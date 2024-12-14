# -*-coding:utf-8-*-
import json
import os
import asyncio

import http.cookies
import re

from downloader.imagedownloader import ImageDownloader

http.cookies._is_legal_key = lambda _: True


from Tool import ClientPool


class Analyzer:
    """
    下载图片
    TODO 下载小说

    Attributes:
        __proxies: Proxy to use aiohttp to send HTTP requests (optional)
        __event: The stop event
        db: The database connection of MongoDB(async)
        cookies: The cookies when a request is sent to pixiv
        host_path: The root path where the image to be saved
        download_type: The type of work to be downloaded
        backup_collection: A collection of backup of info(async)
        logger: The instantiated object of logging.Logger
        progress_signal: The pyqtSignal of QProgressBar
        headers: The headers when sending a HTTP request to pixiv
        timeout: The timeout period for aiohttp requests
        semaphore: The concurrent semaphore of asyncio
    """

    __event = asyncio.Event()
    headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
        "referer": "https://www.pixiv.net/",
    }

    def __init__(
        self,
        host_path: str,
        clientpool: ClientPool,
        download_type: dict,
        semaphore: asyncio.Semaphore,
        backup_collection,
        followings_collection,
        logger,
    ) -> None:
        self.host_path = host_path
        self.download_type = download_type
        self.backup_collection = backup_collection
        self.followings_collection = followings_collection
        self.logger = logger
        self.__event.set()
        self.image_downloader = ImageDownloader(
            clientpool=clientpool,
            semaphore=semaphore,
            backup_collection=backup_collection,
            logger=logger,
        )

    async def start_download(self):
        await self._start_user_download()
        await self._start_following_download()

    async def _start_user_download(self):
        """
        从mongodb中获取图片url并放进协程队列
        """
        # TODO 更新
        self.logger.info("开始下载作者头像")
        tasks = []
        cursor = self.followings_collection.find({"userId": {"$exists": True}})
        async for doc in cursor:
            if not self.__event.is_set():
                await cursor.close()
                return
            tasks.clear()
            if doc.get("not_following_now"):
                continue

            doc["type"] = "user"
            for info in self._info_maker(doc=doc):
                # info = (uid, url, referer_url, path, farmes)
                if not self.__event.is_set():
                    await cursor.close()
                    return
                # print(info)
                # continue

                # 检测保存路径是否存在,不存在则创建
                if os.path.isdir(self.host_path + "/userprofileimage/") is False:
                    os.makedirs(self.host_path + "/userprofileimage/")
                # 检测是否已下载
                if not os.path.isfile(path=info[3]):
                    tasks.append(
                        asyncio.create_task(
                            self.image_downloader.download_image(
                                id=info[0],
                                url=info[1],
                                referer_url=info[2],
                                save_path=info[3],
                                frames=info[4],
                            )
                        )
                    )
            if tasks:
                await asyncio.gather(*tasks)
        await cursor.close()
        self.logger.info("作者头像下载完成！")

    async def _start_following_download(self):
        """
        从mongodb中获取图片url并放进协程队列
        """
        self.logger.info(
            "开始下载\n由于需要读取数据库信息并检测是否下载,所以可能等待较长时间"
        )
        tasks = []
        """
        import motor.motor_asyncio
        a = motor.motor_asyncio.AsyncIOMotorClient()
        a = a['s']
        self.backup_collection = a['']
        """
        cursor = self.backup_collection.find(
            {"id": {"$exists": True}}, no_cursor_timeout=True
        )
        async for doc in cursor:
            if not self.__event.is_set():
                await cursor.close()
                return
            tasks.clear()
            if doc.get("failcode"):
                continue
            type = doc.get("type")
            if not self.download_type.get(type):
                self.logger.warning(
                    "作品:%s---类型%s不在下载范围内" % (doc.get("id"), type)
                )
                continue
            if type == "illust":
                continue
            if type == "manga":
                continue
            if type == "ugoira":
                continue
            uid = doc.get("userId")
            # print(doc)
            for info in self._info_maker(doc=doc):
                # info = (id, url, referer_url, path, farmes)
                # print(info)
                # continue

                if not self.__event.is_set():
                    await cursor.close()
                    return

                # 检测保存路径是否存在,不存在则创建
                if os.path.isdir(self.host_path + "/picture/" + uid + "/") is False:
                    os.makedirs(self.host_path + "/picture/" + uid + "/")
                if os.path.isdir(self.host_path + "/novelcover/") is False:
                    os.makedirs(self.host_path + "/novelcover/")
                # 检测是否已下载
                if not os.path.isfile(path=info[3]):
                    tasks.append(
                        asyncio.create_task(
                            self.image_downloader.download_image(
                                id=info[0],
                                url=info[1],
                                referer_url=info[2],
                                save_path=info[3],
                                frames=info[4],
                            )
                        )
                    )
            # break
            if tasks:
                await asyncio.gather(*tasks)
        await cursor.close()
        self.logger.info("下载完成")

    def _info_maker(self, doc: dict) -> list[tuple]:
        farmes = []
        infos = []
        if (doc["type"] == "illust") or (doc["type"] == "manga"):
            id = str(doc["id"])
            referer_url = "https://www.pixiv.net/artworks/{}".format(id)
            urls = doc["original_url"]
            paths = doc["relative_path"]
            assert len(paths) > 0
            for i in range(len(urls)):
                try:
                    url = urls[i]
                    path = self.host_path + paths[i]
                except Exception:
                    print(doc)
                    continue
                info = (id, url, referer_url, path, farmes)
                infos.append(info)
        elif doc["type"] == "ugoira":
            id = str(doc["id"])
            referer_url = "https://www.pixiv.net/artworks/{}".format(id)
            url = doc["original_url"][0]
            path = "{}/{}".format(self.host_path, doc["relative_path"][0])
            farmes = doc["frames"]
            info = (id, url, referer_url, path, farmes)
            infos.append(info)
        elif doc["type"] == "novel":
            id = str(doc["id"])
            url = doc["coverUrl"]
            referer_url = "https://www.pixiv.net/"
            path = "{}novelcover/{}{}".format(
                self.host_path,
                id,
                re.search(r"\.(jpg|jpeg|png|gif)", url).group(0),
            )
            info = (id, url, referer_url, path, farmes)
            infos.append(info)
        elif doc["type"] == "user":
            uid = doc["userId"]
            url = doc["profileImageUrl"]
            referer_url = "https://www.pixiv.net/"
            path = "{}userprofileimage/{}{}".format(
                self.host_path, uid, re.search(r"\.(jpg|jpeg|png|gif)", url).group(0)
            )
            info = (uid, url, referer_url, path, farmes)
            infos.append(info)
        else:
            raise Exception("数据错误！", doc)
        return infos
