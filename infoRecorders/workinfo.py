import asyncio
import json
import logging
import re
import time

from parsel import Selector
from Tool import ClientPool
from motor import motor_asyncio


class WorkInfoRecorder:
    """
    Get information about works

    Use asyncio and httpx

    Attributes:
        __version: Parameters in the Pixiv request link (usefulness unknown)
        __proxies: Proxy to use aiohttp to send HTTP requests (optional)
        __event: The stop event
        db: The database connection of MongoDB(async)
        cookies:The cookies when a request is sent to pixiv
        download_type: The type of work to be downloaded
        backup_collection: A collection of backup of info(async)
        logger: The instantiated object of logging.Logger
        progress_signal: The pyqtSignal of QProgressBar
        headers: The headers when sending a HTTP request to pixiv
        timeout: The timeout period for aiohttp requests
        semaphore: The concurrent semaphore of asyncio
    """

    __version = "54b602d334dbd7fa098ee5301611eda1776f6f39"
    __event = asyncio.Event()
    headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
        "referer": "https://www.pixiv.net/",
    }

    def __init__(
        self,
        clientpool: ClientPool,
        download_type: dict,
        asyncdb: motor_asyncio.AsyncIOMotorDatabase,
        asyncbackupcollection: motor_asyncio.AsyncIOMotorCollection,
        logger: logging.Logger,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.db = asyncdb
        self.download_type = download_type
        self.backup_collection = asyncbackupcollection
        self.followings_collection = self.db["All Followings"]
        self.logger = logger
        self.clientpool = clientpool
        self.semaphore = semaphore
        self.info_recorder = InfoRecorder(
            clientpool=clientpool,
            logger=logger,
            semaphore=semaphore,
            tags_collection=self.db["All Tags"],
            followings_collection=self.followings_collection,
        )
        self.__event.set()
        self.error_counter = 0
        self.logger.info("实例化 work info Recorder 完成!")

    async def start_get_info(self) -> bool | None:
        finish = await self.record_user_work_infos()
        if finish:
            success = await self.mongoDB_auto_backup()
            if success:
                return True
            else:
                return False
                # raise Exception("database backup error")

    async def record_user_work_infos(self) -> bool:
        _painters = self.followings_collection.find({"userId": {"$exists": True}})
        painters = []
        async for painter in _painters:
            if painter.get("not_following_now"):
                continue
            else:
                painters.append(painter)
        for painter in painters:
            uid = painter.get("userId")
            name = painter.get("userName")
            name, ids = await self.get_user_work_id(user=(uid, name))
            collection = self.db[name]
            if ids:
                # 将作品详情信息保存在mongodb中
                async with self.semaphore:
                    exists = collection.find(
                        {"id": {"$exists": True}}, {"_id": 0, "id": 1}
                    )
                    exists_id = [id.get("id") async for id in exists]
                    for key in list(ids.keys()):
                        if not self.__event.is_set():
                            return
                        _ids = ids.get(key)
                        task_list = []
                        for _id in _ids:
                            if int(_id) in exists_id:
                                continue
                            _recorder = self.info_recorder.record_in_Db(
                                work_id=_id, work_type=key, collection=collection
                            )
                            task = asyncio.create_task(_recorder)
                            task_list.append(task)
                        futurelist = await asyncio.gather(*task_list)
                        for res in futurelist:
                            if not self.__event.is_set():
                                return
            else:
                print("No Ids!")

        if not self.__event.is_set():
            return False
        else:
            self.logger.info("获取所有作者的作品信息完成")
            return True

    async def get_user_work_id(self, user: tuple[str, str]) -> tuple[str, dict]:
        async with self.semaphore:
            """获取作者所有作品的id"""
            Ids = {}
            uid, name = user
            self.logger.info("获取%s(uid:%s)的作品信息......" % (name, uid))
            self.headers.update(
                {"referer": "https://www.pixiv.net/users/{}".format(uid)}
            )
            xhr_url = "https://www.pixiv.net/ajax/user/{}/profile/all?lang=zh&version={}".format(
                uid, self.__version
            )
            _retry = False
            while True:
                returncode, ids_json = await self.clientpool.send_get_request(
                    xhr_url, uid, isretry=_retry
                )
                if returncode == 1:
                    # 防封号
                    time.sleep(0.6)
                    return None
                elif returncode == 2:
                    _retry = True
                    self.logger.info("自动重试......")
                    time.sleep(2)
                    continue
                elif returncode == 3:
                    # TODO
                    pass
                elif returncode == 4:
                    self.logger.warning("正在自动终止程序......")
                    # TODO
                    exit(0)
                else:
                    break
            # print(ids_json)
            body = ids_json.get("body")
            # print(body)
            if isinstance(body, dict) is not True:
                # raise Exception('[ERROR]获取ID失败!',body)
                # print("[ERROR]获取ID失败!")
                # print(ids_json)
                self.logger.error("获取ID失败!\nIds:%s" % str(ids_json))
                return None
            # 插图
            illusts = []
            _illusts = body.get("illusts")
            # print(_illusts)
            if isinstance(_illusts, dict) and _illusts is not None:
                illusts = [*_illusts]
            elif isinstance(_illusts, list) and (len(_illusts) == 0):
                pass
            else:
                raise Exception("[ERROR]获取插画失败!")
            # 漫画
            manga = []
            _mangas = body.get("manga")
            if isinstance(_mangas, dict) and _mangas is not None:
                manga = [*_mangas]
            elif isinstance(_mangas, list) and (len(_mangas) == 0):
                pass
            else:
                raise Exception("[ERROR]获取漫画失败!")
            # 小说
            novels = []
            _novels = body.get("novels")
            if isinstance(_novels, dict) and _novels is not None:
                novels = [*_novels]
            elif isinstance(_novels, list) and (len(_novels) == 0):
                pass
            else:
                raise Exception("[ERROR]获取小说失败!")
            # 漫画系列
            mangaSeries = str(re.findall("'mangaSeries'.*?}]", str(ids_json), re.S))
            # 小说系列
            novelSeries = str(re.findall("'novelSeries'.*?}]", str(ids_json), re.S))

            # return ids
            if len(illusts) != 0 and self.download_type.get("illust"):
                Ids["illusts"] = illusts
            if len(manga) != 0 and self.download_type.get("manga"):
                Ids["manga"] = manga
            if len(novels) != 0 and self.download_type.get("novel"):
                Ids["novels"] = novels
            if len(mangaSeries) != 0 and self.download_type.get("mangaSeries"):
                mangaSeries_1 = str(re.findall("'id':.*?,", mangaSeries, re.S))
                mangaSeries_ids = re.findall("[0-9]+", mangaSeries_1, re.S)
                Ids["mangaSeries"] = mangaSeries_ids
            if len(novelSeries) != 0 and self.download_type.get("novelSeries"):
                novelSeries_1 = str(re.findall("'id':.*?,", novelSeries, re.S))
                novelSeries_ids = re.findall("[0-9]+", novelSeries_1, re.S)
                Ids["novelSeries"] = novelSeries_ids

            return (name, Ids)

    async def mongoDB_auto_backup(self) -> bool:
        self.logger.info("开始自动备份,请勿关闭程序!!!")
        names = await self.db.list_collection_names()
        for name in names:
            collection = self.db[name]
            # 可不用
            async with self.semaphore:
                async for docs in collection.find(
                    {"id": {"$exists": True}}, {"_id": 0}
                ):
                    if not self.__event.is_set():
                        self.logger.info("停止自动备份!")
                        return False
                    if len(docs) >= 9:
                        b = await self.backup_collection.find_one(
                            {"id": docs.get("id")}
                        )
                        if b:
                            continue
                        else:
                            await self.backup_collection.insert_one(docs)
                            # print(c)
        self.logger.info("自动备份完成!")
        return True

    def set_version(self, version: str):
        self.__version = version

    def stop_getting(self):
        self.__event.clear()
        self.logger.info("停止获取作者的作品信息......")


class InfoRecorder:
    def __init__(
        self,
        clientpool: ClientPool,
        logger: logging.Logger,
        semaphore: asyncio.Semaphore,
        tags_collection: motor_asyncio.AsyncIOMotorCollection,
        followings_collection: motor_asyncio.AsyncIOMotorCollection,
    ):
        self.clientpool = clientpool
        self.logger = logger
        self.semaphore = semaphore
        self.tags_collection = tags_collection
        self.followings_collection = followings_collection

    async def _get_info(self, work_id: str, work_type) -> dict | None:
        """
        Get detailed information about a work

        Args:
            url(str): Request link
            id(str): The ID of the work
            session(aiohttp.ClientSession): Connection session with pixiv

        Returns:

            A dictionary of work information. Include the ID, title, description,
            tags, download link of the original image (if it is an image), author ID,
            author's name, and relative storage path. For example:

            {"id": 100774433,
                "title": "夏生まれ",
                "description": "らむねちゃん応援してます(๑╹ᆺ╹)",
                "tags": {
                    "バーチャルYouTuber": "虚拟主播",
                    "ぶいすぽっ!": "Virtual eSports Project",
                    "白波らむね": "Shiranami Ramune",
                    "可愛い": "可爱",
                    "夏": "夏天",
                    "海": "sea",
                    "女の子": "女孩子",
                    "青髪": None
                },
                "original_url": [
                    "https://i.pximg.net/img-original/img/2022/08/26/19/00/13/100774433_p0.png"
                ],
                "userId": "9155411",
                "username": "rucaco/るかこ",
                "relative_path": [
                    "picture/9155411/100774433_p0.png"
                ]
            }

        Raises:
            Exception: The parsing method is incorrect
        """
        async with self.semaphore:

            _retry = False
            while True:
                if (work_type == "illusts") or (work_type == "manga"):
                    self.logger.info("获取插画信息......ID:%s" % work_id)
                    returncode, work_html = await self.clientpool.send_get_request(
                        "https://www.pixiv.net/artworks/" + work_id,
                        work_id,
                        isjson=False,
                        isretry=_retry,
                    )
                elif work_type == "novels":
                    self.logger.info("获取小说信息......ID:%s" % work_id)
                    returncode, work_html = await self.clientpool.send_get_request(
                        "https://www.pixiv.net/novel/show.php?id=" + work_id,
                        work_id,
                        isjson=False,
                        isretry=_retry,
                    )
                elif work_type == "series":
                    self.logger.info("获取系列信息......ID:%s" % work_id)
                    returncode, work_html = await self.clientpool.send_get_request(
                        "https://www.pixiv.net/" + work_type + "/series/" + work_id,
                        work_id,
                        isjson=False,
                        isretry=_retry,
                    )
                else:
                    raise Exception()
                if returncode == 1:
                    # 防封号
                    time.sleep(0.6)
                    return None
                elif returncode == 2:
                    _retry = True
                    self.logger.info("自动重试......")
                    time.sleep(2)
                    continue
                elif returncode == 3:
                    # TODO
                    return None
                elif returncode == 4:
                    self.logger.warning("正在自动终止程序......")
                    # TODO
                    exit(0)
                else:
                    # print(returncode)
                    # print(work_html)
                    infoparsel = InfoParsel(work_html, self.clientpool, self.logger)
                    info = await infoparsel.get_result()
                    if info is not None:
                        break
                    else:
                        # self.logger.warning("获取的html异常!")
                        # self.logger.debug(work_html)
                        if _retry:
                            time.sleep(2)
                            return None
                        else:
                            _retry = True
                            self.logger.info("自动重试......")
                            time.sleep(2)
                            continue

            # print(info)
            return info

    async def record_in_Db(self, work_id: str, work_type, collection):
        info = await self._get_info(work_id=work_id, work_type=work_type)
        res = await collection.insert_one(info)
        assert res, "记录info失败------%s" % info
        await self._record_in_tags(info.get("id"), info.get("tags"))
        await self._record_in_user(userName=info["username"], info=info)
        time.sleep(0.6)
        return None

    async def _record_in_tags(self, id: int, tags: dict) -> None:
        # TODO 检查
        for name, translate in tags.items():
            earlier = await self.tags_collection.find_one({"name": name})
            if earlier:
                workids = earlier.get("workids")
                if workids:
                    if id not in workids:
                        workids.append(id)
                else:
                    workids = [id]
                works_count = earlier.get("works_count") + 1
                earlier_translate = earlier.get("translate")
                if earlier_translate is None and translate:
                    await self.tags_collection.update_one(
                        {"name": name},
                        {
                            "$set": {
                                "translate": translate,
                                "works_count": works_count,
                                "workids": workids,
                            }
                        },
                    )
                elif earlier_translate and translate:
                    if translate in earlier_translate.split("||"):
                        await self.tags_collection.update_one(
                            {"name": name},
                            {"$set": {"works_count": works_count, "workids": workids}},
                        )
                    else:
                        await self.tags_collection.update_one(
                            {"name": name},
                            {
                                "$set": {
                                    "translate": earlier_translate + "||" + translate,
                                    "works_count": works_count,
                                    "workids": workids,
                                }
                            },
                        )
                elif (earlier_translate and translate) is None:
                    await self.tags_collection.update_one(
                        {"name": name},
                        {"$set": {"works_count": works_count, "workids": workids}},
                    )
                else:
                    print(id)
                    return
            else:
                res = await self.tags_collection.insert_one(
                    {
                        "name": name,
                        "translate": translate,
                        "works_count": 1,
                        "workids": [id],
                    }
                )
                assert res, "记录tag失败------%s" % id

    async def _record_in_user(self, userName: str, info: dict) -> None:
        userinfo = await self.followings_collection.find_one({"userName": userName})
        earlier_newest_works = userinfo.get("newestWorks")
        if earlier_newest_works is None:
            assert await self.followings_collection.find_one_and_update(
                {"userName": userName}, {"$set": {"newestWorks": [info]}}
            )
        else:
            earlier_newest_works.append(info)
            newest_works = sorted(
                earlier_newest_works, key=self.timeconverter, reverse=True
            )
            if len(newest_works) > 4:
                newest_works.pop(4)
            assert await self.followings_collection.update_one(
                {"userName": userName}, {"$set": {"newestWorks": newest_works}}
            )

    def timeconverter(self, dict_item) -> int:
        uploadDate = dict_item["uploadDate"]
        inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
        return inttime


class InfoParsel:
    def __init__(self, work_html: str, clientpool: ClientPool, logger) -> None:
        self.clientpool = clientpool
        self.logger = logger
        selector = Selector(text=work_html)
        preload_datas = selector.xpath('//meta[@id="meta-preload-data"]/@content').get()
        # or re.search("error-message", work_html, re.S)
        if not preload_datas:
            logger.warning("解析方式可能错误")
            return None
        info_json = json.loads(preload_datas, strict=False)
        # print(info_json)
        infos = info_json.items()
        assert len(infos) == 3, "解析方式错误------all"
        _infos = []
        for _info in infos:
            _infos.append(_info)
        self.infos = _infos[1]
        del _infos

        self.logger.debug("解析作品信息......")
        self.work_id, work_info = self.infos[1].popitem()
        # 判断作品类型
        if self.infos[0] == "illust":
            work_type = work_info.get("illustType")
            if work_type == 0:
                self.work_type = "illust"
            elif work_type == 1:
                self.work_type = "manga"
            elif work_type == 2:
                self.work_type = "ugoira"
            self.work_info = work_info
        elif self.infos[0] == "novel":
            self.work_type = "novel"
            self.work_info = work_info
        # 共有作品信息
        tags = {}
        for text in self.work_info.get("tags").get("tags"):
            tag = text.get("tag")
            translation = text.get("translation")
            if translation:
                translation = translation.get("en")
            tags.update({tag: translation})

        self.main_info = {
            "type": self.work_type,  # 作品类型
            "id": int(self.work_id),  # 作品id
            "title": self.work_info.get("title"),  # 作品标题
            "description": self.work_info.get("description"),  # 作品描述
            "tags": tags,  # 作品标签
            "userId": self.work_info.get("userId"),  # 作者id
            # TODO 改为userName
            "username": self.work_info.get("userName"),  # 作者名字
            "uploadDate": self.work_info.get("uploadDate"),  # 上传日期
            "likeData": self.work_info.get("likeData"),  # 我的点赞信息
            "likeCount": self.work_info.get("likeCount"),  # 点赞数
            "bookmarkCount": self.work_info.get("bookmarkCount"),  # 收藏数
            "viewCount": self.work_info.get("viewCount"),  # 浏览数
            "isOriginal": self.work_info.get("isOriginal"),  # 原创作品
            "aiType": self.work_info.get("aiType"),  # 是否使用ai
        }

    async def fetch_artworks_links(self) -> dict:
        # ====================================
        #             获取原图链接
        # ====================================
        # 原图链接
        original_urls = []
        # 图片保存路径
        relative_path = []
        if (self.work_type == "illust") or (self.work_type == "manga"):
            xhr_url = "https://www.pixiv.net/ajax/illust/%s/pages?" % self.work_id
        elif self.work_type == "ugoira":
            xhr_url = "https://www.pixiv.net/ajax/illust/%s/ugoira_meta?" % self.work_id
        else:
            return None
        # headers = {
        #      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) \
        #         AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
        #     "referer": "https://www.pixiv.net/artworks/%s" % self.work_id}
        # params = {"lang": "zh"}
        # "version": "54b602d334dbd7fa098ee5301611eda1776f6f39"}
        # headers.update(
        #     {"referer": "https://www.pixiv.net/artworks/%d" % work_id})
        # requests = client.build_request("GET", xhr_url, params=params, headers=headers)
        # print(str(requests.url))
        _retry = False
        while True:
            returncode, img_json = await self.clientpool.send_get_request(
                xhr_url, self.work_id, isretry=_retry
            )
            # print(returncode, img_json)
            if returncode == 1:
                # 防封号
                time.sleep(0.6)
                return None
            elif returncode == 2:
                _retry = True
                self.logger.info("自动重试......")
                time.sleep(2)
                continue
            elif returncode == 3:
                # TODO
                return None
            elif returncode == 4:
                self.logger.warning("正在自动终止程序......")
                # TODO
                exit(0)
            else:
                break
        body = img_json.get("body")
        if (self.work_type == "illust") or (self.work_type == "manga"):
            for one in body:
                urls = one.get("urls")
                original = urls.get("original")
                name = re.search(r"[0-9]+\_.*", original).group()
                relative_path.append("picture/" + self.main_info["userId"] + "/" + name)
                original_urls.append(original)
        elif self.work_type == "ugoira":
            # print(body)
            originalSrc = body.get("originalSrc")
            original_urls.append(originalSrc)
            name = re.search(r"[0-9]+\_ugoira", originalSrc).group()
            name = re.sub("_ugoira", ".gif", name)
            relative_path.append("picture/" + self.main_info["userId"] + "/" + name)
            frames = body.get("frames")
            self.main_info.update({"frames": frames})
        self.main_info.update(
            {"original_url": original_urls, "relative_path": relative_path}
        )
        for key in self.main_info:
            if self.main_info.get(key) is None and key != "description":
                raise Exception("解析方式错误---%s" % self.main_info)
        # 防封号
        time.sleep(0.6)
        # print(info)
        return self.main_info

    def fetch_novel(self):
        self.main_info["content"] = self.work_info.get("content")  # 小说文本
        self.main_info["coverUrl"] = self.work_info.get("coverUrl")  # 小说封面
        self.main_info["characterCount"] = self.work_info.get(
            "characterCount"
        )  # 小说字数
        for key in self.main_info:
            if self.main_info.get(key) is None and key != "description":
                raise Exception("解析方式错误---%s" % self.main_info)
        return self.main_info

    def fetch_series(self):
        pass

    async def get_result(self):
        result = None
        try:
            if (
                (self.work_type == "illust")
                or (self.work_type == "manga")
                or (self.work_type == "ugoria")
            ):
                result = await self.fetch_artworks_links()
            elif self.work_type == "novel":
                result = self.fetch_novel()
            else:
                print(6)
            return result
        except AttributeError:
            return result


if __name__ == "__main__":
    newest_works = [
        {
            "type": "novel",
            "id": 8187018,
            "uploadDate": "2017-09-12T08:55:24+00:00",
        },
        {
            "type": "novel",
            "id": 10727287,
            "uploadDate": "2019-02-09T15:07:42+00:00",
        },
        {
            "type": "novel",
            "id": 9155342,
            "uploadDate": "2018-01-24T03:51:13+00:00",
        },
        {
            "type": "novel",
            "id": 21933141,
            "uploadDate": "2024-04-11T15:21:48+00:00",
        },
    ]

    def timeconverter(dict_item) -> int:
        uploadDate = dict_item["uploadDate"]
        inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
        return inttime

    sl = sorted(newest_works, key=timeconverter, reverse=True)
    sl.insert(0, {"fff": 555})
    sl.pop(4)
    print(sl)
    "2017-09-12T08:55:24+00:00"
