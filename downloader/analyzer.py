# -*-coding:utf-8-*-
import os
import asyncio
import re

from downloader.imagedownloader import ImageDownloader
from Tool import ClientPool
from mongoDB_hander import MongoDBHander


class Analyzer:
    """
    分析mongoDB中的数据,然后传递给ImageDownloader下载

    Attributes:
        __event: The stop event
        host_path: The root path where the image to be saved
        clientpool: ClientPool
        download_type: The type of work to be downloaded
        backup_collection: A collection of backup of info(async)
        followings_collection: A collection of user you following(async)
        semaphore: The concurrent semaphore of asyncio
        logger: The instantiated object of logging.Logger
    """

    __event = asyncio.Event()

    def __init__(
        self,
        host_path: str,
        clientpool: ClientPool,
        download_type: dict,
        semaphore: asyncio.Semaphore,
        mongoDb_hander: MongoDBHander,
        logger,
    ) -> None:
        self.host_path = host_path
        self.download_type = download_type
        self.mongoDb_hander = mongoDb_hander
        self.logger = logger
        self.__event.set()
        self.image_downloader = ImageDownloader(
            clientpool=clientpool,
            semaphore=semaphore,
            mongoDb_hander=mongoDb_hander,
            logger=logger,
        )

    async def start_download(self):
        success: bool = await self._start_user_download()
        if not success:
            pass
        await self._start_following_download()

    async def _start_user_download(self) -> bool:
        """
        下载作者的头像
        """
        # TODO 更新
        self.logger.info("开始下载作者头像")
        # 检测保存路径是否存在,不存在则创建
        if not os.path.isdir(self.host_path + "/userprofileimage/"):
            os.makedirs(self.host_path + "/userprofileimage/")
        tasks = []
        async for doc in self.mongoDb_hander.find_exist(
            key="userId", collection="followings"
        ):
            if not self.__event.is_set():
                return False
            tasks.clear()
            # 跳过已经取消关注的作者
            if doc.get("not_following_now"):
                continue

            doc["type"] = "user"
            for info in self._info_maker(doc=doc):
                # info = (uid, url, referer_url, path, farmes)
                if not self.__event.is_set():
                    return False
                # print(info)
                # continue

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
        self.logger.info("作者头像下载完成！")
        return True

    async def _start_following_download(self):
        """
        下载关注的作者的图片
        """
        self.logger.info(
            "开始下载\n由于需要读取数据库信息并检测是否下载,所以可能等待较长时间"
        )
        # 检测保存路径是否存在,不存在则创建
        if not os.path.isdir(self.host_path + "/novelcover/"):
            os.makedirs(self.host_path + "/novelcover/")
        tasks = []
        async for doc in self.mongoDb_hander.find_exist(key="id", collection="backup"):
            if not self.__event.is_set():
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
            # if type == "illust":
            #     continue
            # if type == "manga":
            #     continue
            # if type == "ugoira":
            #     continue
            uid = doc.get("userId")
            # print(doc)
            for info in self._info_maker(doc=doc):
                # info = (id, url, referer_url, path, farmes)
                # print(info)
                # continue

                if not self.__event.is_set():
                    return

                # 检测保存路径是否存在,不存在则创建
                if not os.path.isdir(self.host_path + "/picture/" + uid + "/"):
                    os.makedirs(self.host_path + "/picture/" + uid + "/")
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
        self.logger.info("下载完成")

    def _info_maker(self, doc: dict) -> list[tuple]:
        """分析信息,生成下载链接和保存路径"""
        farmes: list[int] = []
        infos: list[tuple] = []
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
            path = "{host_path}novelcover/{id}{format}".format(
                host_path=self.host_path,
                id=id,
                format=re.findall(r"\.(jpg|jpeg|png|gif)", url)[0],
            )
            info = (id, url, referer_url, path, farmes)
            infos.append(info)
        elif doc["type"] == "user":
            uid = doc["userId"]
            url = doc["profileImageUrl"]
            referer_url = "https://www.pixiv.net/"
            path = "{host_path}userprofileimage/{uid}.{format}".format(
                host_path=self.host_path,
                uid=uid,
                format=re.findall(r"\.(jpg|jpeg|png|gif)", url)[0],
            )
            info = (uid, url, referer_url, path, farmes)
            infos.append(info)
        else:
            raise Exception("数据错误！", doc)
        return infos

    def stop_downloading(self):
        self.__event.clear()
        self.image_downloader.stop_downloading()
        self.logger.info("停止下载")
        return
