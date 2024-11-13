# -*-coding:utf-8-*-
import json
import os
import re
import time
import asyncio
import zipfile
from PIL import Image

import http.cookies
http.cookies._is_legal_key = lambda _: True


from Tool import ClientPool

class DownloaderHttpx:
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
    "referer": "https://www.pixiv.net/"}

    def __init__(self, host_path: str, clientpool: ClientPool, download_type: dict, semaphore: asyncio.Semaphore, backup_collection, logger) -> None:
        self.host_path = host_path
        self.download_type = download_type
        self.backup_collection = backup_collection
        self.logger = logger
        self.clientpool = clientpool
        self.semaphore = semaphore
        self.__event.set()

    async def start_work_download(self, id):
        """
        从图片url下载
        """
        print("开始下载")
        tasks = []
        infogetter = infofetcher.InfoGetterOld(
            self.cookies, self.download_type, None, self.backup_collection
        )
        infos = infogetter.get_info(
            url="https://www.pixiv.net/artworks/" + id, id=id)
        del infogetter
        urls = infos.get("original_url")
        relative_path = []
        # 检测下载路径是否存在,不存在则创建
        if os.path.isdir(self.host_path + "works/" + id + "/") is False:
            os.makedirs(self.host_path + "works/" + id + "/")
        async with self.semaphore:
            for a in range(len(urls)):
                if not self.__event.is_set():
                    return
                url = urls[a]
                name = re.search(r"[0-9]+\_.*", url).group()
                path = self.host_path + "works/" + id + "/" + name
                relative_path.append("works/" + id + "/" + name)
                # 检测是否已下载
                if not os.path.isfile(path=path):
                    info = (id, url, path)
                    tasks.append(asyncio.create_task(
                        self.stream_download(info, path)))
            infos.update({"relative_path": relative_path})
            with open(
                "{}works/{}/info.json".format(self.host_path, id), "w", encoding="utf-8"
            ) as f:
                json.dump(infos, f, ensure_ascii=False, indent=4)
            await asyncio.wait(tasks)

        print("下载完成")

    def start_tag_download(self):
        """
        从pixiv获取含标签的图片下载
        """

    async def start_following_download(self):
        """
        从mongodb中获取图片url并放进协程队列
        """
        self.logger.info("开始下载\n由于需要读取数据库信息并检测是否下载,所以可能等待较长时间")
        tasks = []
        '''
        import motor.motor_asyncio
        a = motor.motor_asyncio.AsyncIOMotorClient()
        a = a['s']
        self.backup_collection = a['']
        '''
        cursor = self.backup_collection.find({"id": {"$exists": True}}, no_cursor_timeout=True)
        async for doc in cursor:
            if not self.__event.is_set():
                await cursor.close()
                return
            tasks.clear()
            if doc.get("failcode"):
                continue
            type = doc.get("type")
            if not self.download_type.get(type):
                    self.logger.warning("作品:%s---类型%s不在下载范围内" % (doc.get("id"), type))
                    continue
                # print(doc)
            id = doc.get("id")
            urls = doc.get("original_url")
            uid = doc.get("userId")
            paths = doc.get("relative_path")
            if len(paths) < 1:
                self.logger.warning("数据错误:\n%s" % str(doc))
                continue

            for a in range(len(urls)):
                if not self.__event.is_set():
                    await cursor.close()
                    return
                try:
                    url = urls[a]
                    path = self.host_path + paths[a]
                except Exception:
                    print(doc)
                    continue

                # 检测保存路径是否存在,不存在则创建
                if os.path.isdir(self.host_path + "/picture/" + uid + "/") is False:
                    os.makedirs(self.host_path + "/picture/" + uid + "/")
                # 检测是否已下载
                if not os.path.isfile(path=path):
                    if type == 'ugoira':
                        info = (id, url, path, doc.get('frames'))
                    else:
                        info = (id, url, path)
                    tasks.append(asyncio.create_task(
                        self.download_image(info)))
            if tasks:
                await asyncio.gather(*tasks)
        await cursor.close()
        self.logger.info("下载完成")

    async def invalid_image_recorder(self, id, failcode):
        doc = await self.backup_collection.find_one_and_update(
            {"id": id}, {"$set": {"failcode": failcode}}
        )
        if not doc:
            self.logger.error(
                "error in record invaild image:" + id + "\n" + doc)

    async def download_image(self, info: tuple):
        """从队列中获取数据并下载图片"""
        async with self.semaphore:
            if not self.__event.is_set():
                return None
            start_time = time.time()  # 程序开始时间
            # print('获取数据%s'%(info))
            id = str(info[0])
            url = info[1]
            path = info[2]
            _retry = False
            if len(info) == 4:
                # print(info)
                zip_path = id + ".zip"
                image_dir = id + "/"
                frames = info[3]
                img_url = "https://www.pixiv.net/artworks/" + id
                self.headers.update({"referer": img_url})
                self.logger.info("下载动图ID:%s" % id)
                while True:
                    returncode, status_code = await self.clientpool.get_download(self.__event, (id, url, self.headers), zip_path, False, _retry)
                    if returncode == 1:
                        # 防封号
                        # time.sleep(0.6)
                        return None
                    elif returncode == 2:
                        _retry = True
                        self.logger.info("自动重试......")
                        time.sleep(2)
                        continue
                    elif returncode == 3:
                        # TODO
                        # 错误记录，但感觉没什么用
                        self.invalid_image_recorder(id, status_code)
                        return None
                    elif returncode == 4:
                        self.logger.warning("正在自动终止程序......")
                        # TODO
                        exit(0)
                    else:
                        break
                # 解压zip
                with zipfile.ZipFile(zip_path, "r") as f:
                    for file in f.namelist():
                        f.extract(file, image_dir)
                # 删除临时zip文件
                os.remove(zip_path)

                # 创建GIF动图
                image_list = []
                duration = []
                self.logger.info('构造GIF......')
                for frame in frames:
                    image = Image.open(image_dir + frame.get("file"))
                    image_list.append(image)
                    duration.append(frame.get("delay"))
                image_list[0].save(
                    path,
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
                # exit(0)
            else:
                img_url = "https://www.pixiv.net/artworks/" + id
                self.headers.update({"referer": img_url})
                self.logger.info("下载图片:ID:%s" % id)
                while True:
                    returncode, status_code = await self.clientpool.get_download(self.__event, (id, url, self.headers), path, _retry)
                    if returncode == 1:
                        # 防封号
                        # time.sleep(0.6)
                        return None
                    elif returncode == 2:
                        _retry = True
                        self.logger.info("自动重试......")
                        time.sleep(2)
                        continue
                    elif returncode == 3:
                        # TODO
                        # 错误记录，但感觉没什么用
                        self.invalid_image_recorder(id, status_code)
                        return None
                    elif returncode == 4:
                        self.logger.warning("正在自动终止程序......")
                        # TODO
                        exit(0)
                    else:
                        break
            end_time = time.time()  # 程序结束时间
            run_time = end_time - start_time  # 程序的运行时间，单位为秒
            if os.path.exists(path):
                self.logger.info(
                    "下载作品{}完成,耗时:{},保存至:{}".format(id, run_time, path))
            else:
                self.logger.warning("图片保存失败")

    def pause_downloading(self):
        pass

    def stop_downloading(self):
        self.__event.clear()
        self.logger.info("停止下载")
        return
