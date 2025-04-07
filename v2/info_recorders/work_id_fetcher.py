from asyncio import Event, Semaphore, create_task, gather
from common import ClientPool, ResponseHander, ConfigHander, MongoDBHander
from info_recorders.work_info_recorder import WorkInfoRecorder
from typing import Literal
from logging import Logger


class WorkIdFetcher:
    """
    Get work ids and information about works

    Use asyncio and httpx

    Attributes:
        __event: The stop event
        download_type: The type of work to be downloaded
        logger: The instantiated object of logging.Logger
        semaphore: The concurrent semaphore of asyncio
    """

    __event = Event()

    def __init__(
        self,
        config_hander: ConfigHander,
        clientpool: ClientPool,
        mongoDb_hander: MongoDBHander,
        logger: Logger,
        myId: str,
    ):
        logger.info("Initialize work Id fetcher......")
        self.download_type = config_hander.require_config("download_type")
        self.semaphore = Semaphore(config_hander.require_config("semaphore"))
        self.clientpool = clientpool
        self.mongoDb_hander = mongoDb_hander
        self.logger = logger
        self.info_recorder = WorkInfoRecorder(
            clientpool=clientpool,
            logger=logger,
            mongoDb_hander=mongoDb_hander,
        )
        self.myId = myId
        self.__event.set()

    async def start(self) -> bool:
        finish = await self._record_followings_works_info()
        if not finish:
            return False
        finish = await self._record_bookmarked_works_info()
        if not finish:
            return False
        return True
        # return await self.mongoDb_hander.mongoDB_auto_backup()

    async def _record_followings_works_info(self) -> bool:
        _followings = self.mongoDb_hander.find_exist(
            key="userId", collection="followings"
        )
        followings = []
        async for following in _followings:
            if following.get("not_following_now"):
                continue
            else:
                followings.append(following)
        for following in followings:
            if not self.__event.is_set():
                return False
            uid = following["userId"]
            name = following["userName"]
            if not await self._fetch_following_work_id(uid, name):
                return False
        self.logger.info("Fetch all followings'works complete.")
        return True

    async def _fetch_following_work_id(self, uid: str, name: str) -> bool:
        """fetch and record all works'info of the following user"""
        self.logger.info(f"Fetching user: {name} (uid:{uid}) works'info......")
        headers = self.clientpool.headers
        headers.update({"referer": f"https://www.pixiv.net/users/{uid}"})
        response_hander = ResponseHander(self.logger, True)
        response_hander.set_processor({"REQUIRE": "body"})
        response_hander = await self.clientpool.get(
            url=f"https://www.pixiv.net/ajax/user/{uid}/profile/all",
            response_hander=response_hander,
            params=[("lang", "zh")],
        )
        if response_hander.res_code:
            self.logger.warning("Request failed.")
            if response_hander.res_code == 2:
                await self.mongoDb_hander.record_error()
            elif response_hander.res_code == 3:
                self.stop()
            return False
        body = response_hander.processed_response
        # print(body)
        if not isinstance(body, dict):
            # raise Exception('[ERROR]获取ID失败!',body)
            self.logger.error(
                f"Fetch Id failed. User:{name}({uid})\nIds:{response_hander.html}"
            )
            return False

        # illusts
        if self.download_type["illust"]:
            illusts = body.get("illusts")
            if isinstance(illusts, dict):
                if not await self._record_infos(
                    [*illusts],
                    work_type="illust",
                    collection=name,
                ):
                    return False
            elif isinstance(illusts, list) and (len(illusts) == 0):
                pass
            else:
                raise Exception("Illusts parse method error")

        # manga
        if self.download_type["manga"]:
            manga = body.get("manga")
            if isinstance(manga, dict):
                if not await self._record_infos(
                    [*manga],
                    work_type="illust",
                    collection=name,
                ):
                    return False

            elif isinstance(manga, list) and (len(manga) == 0):
                pass
            else:
                raise Exception("Manga parse method error")

        # novels
        if self.download_type["novel"]:
            novels = body.get("novels")
            if isinstance(novels, dict):
                if not await self._record_infos(
                    [*novels],
                    work_type="novel",
                    collection=name,
                ):
                    return False

            elif isinstance(novels, list) and (len(novels) == 0):
                pass
            else:
                raise Exception("Novels parse method error")
        # Series
        if self.download_type["series"]:
            mangaSeries = body.get("mangaSeries")
            novelSeries = body.get("novelSeries")

        return True

    async def _record_bookmarked_works_info(self) -> bool:
        self.logger.info("Fetching bookmarked works'info......")
        res: bool
        res = await self._fetch_bookmarked_work_id("illust", "show")
        if not res:
            return False
        res = await self._fetch_bookmarked_work_id("illust", "hide")
        if not res:
            return False
        res = await self._fetch_bookmarked_work_id("novel", "show")
        if not res:
            return False
        res = await self._fetch_bookmarked_work_id("novel", "hide")
        return res

    async def _fetch_bookmarked_work_id(
        self, work_type: Literal["illust", "novel"], mode: Literal["show", "hide"]
    ) -> bool:
        offset: int = 0
        bookmark_url = (
            f"https://www.pixiv.net/ajax/user/{self.myId}/{work_type}s/bookmarks"
        )
        bookmarked_ids = []
        while True:
            if not self.__event.is_set():
                return False
            response_hander = ResponseHander(self.logger, True)
            response_hander.set_processor({"REQUIRE": "body.works"})
            response_hander = await self.clientpool.get(
                url=bookmark_url,
                response_hander=response_hander,
                params=[
                    ("tag", None),
                    ("offset", offset),
                    ("limit", 48),
                    ("rest", mode),
                    ("lang", "zh"),
                ],
                use_myclient=(mode == "hide"),
            )
            if response_hander.res_code:
                self.logger.warning("Request failed.")
                if response_hander.res_code == 2:
                    await self.mongoDb_hander.record_error()
                elif response_hander.res_code == 3:
                    self.stop()
                return False

            works = response_hander.processed_response
            if not isinstance(works, list):
                return False
            for work in works:
                bookmarked_ids.append(work.get("id"))

            res = await self._record_infos(
                ids=bookmarked_ids,
                work_type=work_type,
                collection="Bookmarks",
                isbookmarked=True,
            )
            if not res:
                return False
            bookmarked_ids.clear()
            if len(works) < 48:
                break
            else:
                offset += 48
        return True

    async def _record_infos(
        self,
        ids: list[str],
        work_type: Literal["illust", "novel"],
        collection: str,
        isbookmarked: bool = False,
    ) -> bool:
        task_list = []
        async with self.semaphore:
            for id in ids:
                if not self.__event.is_set():
                    return False
                if await self.mongoDb_hander.is_exist(
                    key="id", value=int(id), collection=collection
                ):
                    continue
                _recorder = self.info_recorder.record_work_info(
                    work_id=id, work_type=work_type, isbookmarked=isbookmarked
                )
                task = create_task(_recorder)
                task_list.append(task)

                """await self.info_recorder.record_work_info(
                    work_id=id,
                    work_type=work_type,
                )"""
            await gather(*task_list)
            return True

    def stop(self) -> None:
        self.__event.clear()
        self.logger.info("Stop fetching......")
