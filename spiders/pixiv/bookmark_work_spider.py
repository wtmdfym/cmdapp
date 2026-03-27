from data import Request, Response, SpiderResult, ParseError
from utils import ConfigManager
from storage import DataService

from ..base_spider import BaseSpider
from .tools import parse_info, parse_image_links, parse_ugoira_link


class BookmarkWorkSpider(BaseSpider):
    name = "bookmarkwork"
    registry = {"db": "mongodb"}

    def __init__(self, logger, config: ConfigManager, dataservice: DataService):
        super().__init__(logger)
        self.myId = config.require("clientpool_config.primary_account.id")
        self.dataservice = dataservice
        self.init_requests = []
        self.download_type = {"illust", "manga", "novels", "series"}

    async def start(self) -> list[Request]:
        limit = 48
        for work_type in {"illust", "novel"}:
            for mode in {"show", "hide"}:
                self.init_requests.append(
                    Request(
                        "GET",
                        f"https://www.pixiv.net/ajax/user/{self.myId}/{work_type}s/bookmarks",
                        spider_parser=self._parse_work_id,
                        params={
                            "tag": None,
                            "offset": 0,
                            "limit": limit,
                            "rest": mode,
                            "lang": "zh",
                        },
                        use_primary=(mode == "hide"),
                        priority=50,
                        meta={"limit": limit, "work_type": work_type, "mode": mode},
                    )
                )
        return await super().start()

    async def _parse_work_id(self, response: Response) -> SpiderResult:
        """fetch and record all works'info of the following user"""
        meta = response.request.meta
        limit = meta["limit"]
        work_type = meta["work_type"]
        mode = meta["mode"]
        page = meta.get("page", 0)

        body = response.json()["body"]
        if not isinstance(body, dict):
            raise ParseError(
                f"Parse work id failed: {work_type}---{mode}\nResponse: {response.text()}"
            )
        if meta.get("all_page") is not None:
            all_page = meta["all_page"]
        else:
            all_page = (body["total"] + 23) // 24

        spider_result = SpiderResult()

        if all_page <= 0:
            return spider_result

        self.logger.info(
            f"Fetch bookmark works'information---page={page + 1}/{all_page}..."
        )

        works = body["works"]
        if not isinstance(works, list):
            raise ParseError(
                f"Parse work id failed: {work_type}---{mode}\nResponse: {response.text()}"
            )

        if page + 1 < all_page:
            next_page = page + 1
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/user/{self.myId}/{work_type}s/bookmarks",
                    spider_parser=self._parse_work_id,
                    params={
                        "tag": None,
                        "offset": next_page * limit,
                        "limit": limit,
                        "rest": mode,
                        "lang": "zh",
                    },
                    use_primary=(mode == "hide"),
                    priority=50,
                    meta={
                        "limit": limit,
                        "work_type": work_type,
                        "mode": mode,
                        "page": next_page,
                        "all_page": all_page,
                    },
                )
            )

        for work in works:
            work_id = work["id"]
            if await self.dataservice.check_exist_work(work_id):
                self.logger.debug(f"Work: {work_id} exists, skip it.")
                continue

            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/{work_type}/{work_id}",
                    spider_parser=self._parse_work_info,
                    params={"lang": "zh"},
                    priority=40,
                    meta={"work_id": work_id, "work_type": work_type},
                )
            )

        if page + 1 == all_page:
            self.logger.info(
                f"Fetch bookmark works'information {work_type}---{mode} complete."
            )

        return spider_result

    async def _parse_work_info(self, response: Response) -> SpiderResult:
        meta = response.request.meta
        work_id = meta["work_id"]
        work_type = meta["work_type"]
        self.logger.info(f"Fetch {work_type}---{work_id} info")
        spider_result = SpiderResult()

        # pixiv 更新接口
        if work_type == "series":
            raise ParseError("Unused!")
            # info = await self._fetch_series(work_id)

        preload_data = response.json()["body"]
        if not isinstance(preload_data, dict):
            raise ParseError("Load data failed.", preload_data)

        info = parse_info(work_type, preload_data)
        # TODO why not ture?
        info["likeData"] = True

        work_type = info["type"]
        if (work_type == "illust") or (work_type == "manga"):
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/illust/{work_id}/pages",
                    spider_parser=lambda res: parse_image_links(
                        self.logger,
                        self.dataservice,
                        res,
                    ),
                    headers={"referer": f"https://www.pixiv.net/artworks/{work_id}"},
                    params={"lang": "zh"},
                    priority=30,
                    meta={"info": info},
                )
            )
        elif work_type == "ugoira":
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/illust/{work_id}/ugoira_meta",
                    spider_parser=lambda res: parse_ugoira_link(
                        self.logger,
                        self.dataservice,
                        res,
                    ),
                    headers={"referer": f"https://www.pixiv.net/artworks/{work_id}"},
                    params={"lang": "zh"},
                    priority=30,
                    meta={"info": info},
                )
            )
        elif work_type == "novel":
            pass
        else:
            raise ParseError(f"Unknown work type: {work_type}")

        async for item in self.dataservice.record_in_tags(
            id=int(work_id),
            tags=info["tags"],
        ):
            spider_result.items.append(item)

        return spider_result
