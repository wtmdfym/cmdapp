# -*-coding:utf-8-*-
import os
import time
import asyncio
import zipfile
import http.cookies

from PIL import Image
from Tool import ClientPool
from mongoDB_hander import MongoDBHander

http.cookies._is_legal_key = lambda _: True


class ImageDownloader:
    """
    下载图片

    Attributes:
        __event: The stop event
        semaphore: The concurrent semaphore of asyncio
        backup_collection: A collection of backup of info(async)
        logger: The instantiated object of logging.Logger

    """

    __event = asyncio.Event()
    headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
        "referer": "https://www.pixiv.net/",
    }

    def __init__(
        self,
        clientpool: ClientPool,
        semaphore: asyncio.Semaphore,
        mongoDb_hander: MongoDBHander,
        logger,
    ) -> None:
        self.logger = logger
        self.clientpool = clientpool
        self.semaphore = semaphore
        self.mongoDb_hander = mongoDb_hander
        self.__event.set()

    async def invalid_image_recorder(self, id, failcode):
        doc = await self.mongoDb_hander.set_one(
            key="id", value=id, setter={"failcode": failcode}, collection="backup"
        )
        if not doc:
            self.logger.error("error in record invaild image:" + id + "\n" + doc)

    async def download_image(
        self, id: str, url: str, referer_url: str, save_path: str, frames: list
    ):
        """从队列中获取数据并下载图片"""
        async with self.semaphore:
            if not self.__event.is_set():
                return None
            start_time = time.time()  # 程序开始时间
            # 动图
            if len(frames) > 0:
                # print(info)
                zip_path = id + ".zip"
                image_dir = id + "/"
                self.headers.update({"referer": referer_url})
                self.logger.info("下载动图ID:%s" % id)
                success = await self._error_hander(id, url, zip_path)
                if success:
                    # 解压zip
                    with zipfile.ZipFile(zip_path, "r") as f:
                        for file in f.namelist():
                            f.extract(file, image_dir)
                    # 删除临时zip文件
                    os.remove(zip_path)

                    # 创建GIF动图
                    image_list = []
                    duration = []
                    self.logger.info("构造GIF......")
                    for frame in frames:
                        image = Image.open(image_dir + frame.get("file"))
                        image_list.append(image)
                        duration.append(frame.get("delay"))
                    image_list[0].save(
                        save_path,
                        save_all=True,
                        append_images=image_list[1:],
                        optimize=False,
                        duration=duration,
                        loop=0,
                    )
                    # 删除解压图片文件夹
                    for file_name in os.listdir(image_dir):
                        tf = os.path.join(image_dir, file_name)
                        os.remove(tf)
                    os.rmdir(image_dir)
            # 普通图片
            else:
                self.headers.update({"referer": referer_url})
                self.logger.info("下载图片:ID:%s" % id)
                success = await self._error_hander(id, url, save_path)

            if success:
                end_time = time.time()  # 程序结束时间
                run_time = end_time - start_time
                self.logger.info(
                    "下载作品{}完成,耗时:{},保存至:{}".format(id, run_time, save_path)
                )
            else:
                self.logger.warning("图片保存失败")

    async def _error_hander(self, id, url, save_path) -> bool:
        _retry = False
        while True:
            # 防封号
            time.sleep(0.6)
            returncode, status_code = await self.clientpool.get_download(
                self.__event, (id, url, self.headers), save_path, _retry
            )
            if returncode == 1:
                break
            elif returncode == 2:
                _retry = True
                self.logger.info("自动重试......")
                time.sleep(2)
                continue
            elif returncode == 3:
                # TODO
                # 错误记录，但感觉没什么用
                self.invalid_image_recorder(id, status_code)
                break
            elif returncode == 4:
                self.logger.warning("正在自动终止程序......")
                # TODO
                exit(0)
            else:
                if os.path.exists(save_path):
                    return True
        return False

    def pause_downloading(self):
        pass

    def stop_downloading(self):
        self.__event.clear()
        return
