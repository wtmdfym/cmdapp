# -*-coding:utf-8-*-
import os
import re

from download_hander.image_downloader import ImageDownloader
from common import ClientPool, ConfigHander, MongoDBHander
from logging import Logger
from asyncio import Event, Semaphore, create_task, gather


class DownloadHander:
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

    __event = Event()

    def __init__(
        self,
        config_hander: ConfigHander,
        clientpool: ClientPool,
        mongoDb_hander: MongoDBHander,
        logger: Logger,
    ) -> None:
        logger.info("Initialize download hander......")
        self.host_path = config_hander.require_config("host_path")
        self.download_type = config_hander.require_config("download_type")
        self.mongoDb_hander = mongoDb_hander
        self.logger = logger
        self.semaphore = Semaphore(config_hander.require_config("semaphore"))
        self.__event.set()
        self.image_downloader = ImageDownloader(
            clientpool=clientpool,
            semaphore=self.semaphore,
            mongoDb_hander=mongoDb_hander,
            logger=logger,
        )
        # 检测保存路径是否存在,不存在则创建
        if not os.path.isdir(self.host_path + "/userprofileimage/"):
            os.makedirs(self.host_path + "/userprofileimage/")
        if not os.path.isdir(self.host_path + "/picture/"):
            os.makedirs(self.host_path + "/picture/")
        if not os.path.isdir(self.host_path + "/novelcover/"):
            os.makedirs(self.host_path + "/novelcover/")

    async def start(self) -> bool:
        success: bool = await self._start_user_download()
        if not success:
            return False
        success = await self._start_following_download()
        return success

    async def _start_user_download(self) -> bool:
        """
        Download user profile image.
        """
        # TODO 更新
        self.logger.info("Downloading user profile image......")
        tasks = []
        async with self.semaphore:
            async for doc in self.mongoDb_hander.find_exist(
                key="userId", collection="followings"
            ):
                if not self.__event.is_set():
                    return False
                # 跳过已经取消关注的作者
                if doc.get("not_following_now"):
                    continue

                doc["type"] = "user"

                infos = self._info_maker(doc=doc)
                if not infos:
                    return False
                # TODO 信息显示混乱
                tasks.append(create_task(self.async_download_manger(infos)))
                # await
            await gather(*tasks)

        self.logger.info("Download user profile image complete.")
        return True

    async def _start_following_download(self) -> bool:
        """
        Download followings image.
        """
        self.logger.info(
            "Downloading followings image......\n This may take some time to check downloaded image."
        )
        async with self.semaphore:
            async for doc in self.mongoDb_hander.find_exist(
                key="id", collection="backup"
            ):
                if not self.__event.is_set():
                    return False
                if doc.get("failcode"):
                    continue
                work_type = doc.get("type")
                if not self.download_type.get(work_type):
                    self.logger.warning(
                        f"Work {work_type}  ID{doc.get('id')} not in download_type."
                    )
                    continue
                # if type == "illust":
                #     continue
                # if type == "manga":
                #     continue
                # if type == "ugoira":
                #     continue
                # uid = doc.get("userId")
                # print(doc)
                infos = self._info_maker(doc=doc)
                if not infos:
                    return False
                await self.async_download_manger(infos)
        self.logger.info("Download followings image complete.")
        return True

    def _info_maker(self, doc: dict) -> list[tuple] | None:
        """分析信息,生成下载链接和保存路径"""
        farmes: list[int] = []
        infos: list[tuple] = []
        if not doc["type"] == "user":
            if doc["likeData"]:
                # TODO 更改下载信息获取方式
                # creat user works dir
                uid = doc["userId"]
                if not os.path.isdir(f"{self.host_path}/picture/{uid}"):
                    os.makedirs(f"{self.host_path}/picture/{uid}")
                    with open(
                        f"{self.host_path}/picture/{uid}/temporary_dir_for_bookmark_work.txt",
                        mode="w",
                    ) as f:
                        f.write("TEST")
        if (doc["type"] == "illust") or (doc["type"] == "manga"):
            work_id = str(doc["id"])
            referer_url = f"https://www.pixiv.net/artworks/{work_id}"
            urls = doc["original_url"]
            paths = doc["relative_path"]
            assert len(paths) > 0
            for i in range(len(urls)):
                try:
                    url = urls[i]
                    path = self.host_path + paths[i]
                except AttributeError:
                    self.logger.warning(f"Work info incrrocet---{doc}")
                    return
                info = (work_id, url, referer_url, path, farmes)
                infos.append(info)
        elif doc["type"] == "ugoira":
            work_id = str(doc["id"])
            referer_url = f"https://www.pixiv.net/artworks/{work_id}"
            url = doc["original_url"][0]
            path = "{}/{}".format(self.host_path, doc["relative_path"][0])
            farmes = doc["frames"]
            info = (work_id, url, referer_url, path, farmes)
            infos.append(info)
        elif doc["type"] == "novel":
            work_id = str(doc["id"])
            url = doc["coverUrl"]
            referer_url = "https://www.pixiv.net/"
            cover_image_format = re.search(r"\.(jpg|jpeg|png|gif)", url)
            if cover_image_format is None:
                self.logger.error("Cover image format not found.")
                return None
            path = f"{self.host_path}novelcover/{work_id}{cover_image_format.group()}"
            info = (work_id, url, referer_url, path, farmes)
            infos.append(info)
        elif doc["type"] == "user":
            uid = doc["userId"]
            url = doc["profileImageUrl"]
            referer_url = "https://www.pixiv.net/"
            profile_image_format = re.search(r"\.(jpg|jpeg|png|gif)", url)
            if profile_image_format is None:
                self.logger.error("Profile image format not found.")
                return None
            path = (
                f"{self.host_path}userprofileimage/{uid}{profile_image_format.group()}"
            )
            info = (uid, url, referer_url, path, farmes)
            infos.append(info)
            # creat user works dir
            if not os.path.isdir(f"{self.host_path}/picture/{uid}"):
                os.makedirs(f"{self.host_path}/picture/{uid}")
        else:
            raise Exception("Data error!", doc)
        return infos

    async def async_download_manger(self, infos: list):
        tasks = []
        for info in infos:
            # info = (uid, url, referer_url, path, farmes)
            # print(info)
            # continue

            # Check if has been downloaded.
            if not os.path.isfile(path=info[3]):
                tasks.append(
                    create_task(
                        self.image_downloader.download_image(
                            work_id=info[0],
                            url=info[1],
                            referer_url=info[2],
                            save_path=info[3],
                            frames=info[4],
                        )
                    )
                )
        if tasks:
            await gather(*tasks)

    def stop_downloading(self):
        self.__event.clear()
        self.image_downloader.stop()
        self.logger.info("停止下载")
        return
