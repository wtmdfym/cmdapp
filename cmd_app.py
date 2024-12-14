# -*-coding:utf-8-*-
import time
import asyncio
import logging
import sys
import signal
from motor import motor_asyncio
# from InfoFetcher import *
from infoRecorders import FollowingsRecorder,WorkInfoRecorder
from Asyncdownloader import *
from Tool import *


class AsyncThreadingManager():
    '''
    __proxies: Proxy to use requests to send HTTP requests (optional)
    '''

    # break_signal = 
    __proxies = 'http://localhost:1111'
    version = '54b602d334dbd7fa098ee5301611eda1776f6f39'

    def __init__(self, config_dict: dict,  config_save_path, loop: asyncio.AbstractEventLoop, asyncdb,
                 asyncbackupcollection, logger: logging.Logger) -> None:
        super().__init__()
        logger.info("初始化爬虫......")
        self.ifstop = False
        self.config_dict = config_dict
        self.config_save_path = config_save_path
        self.loop = loop
        self.asyncdb = asyncdb
        self.asyncbackup_collection = asyncbackupcollection
        self.logger = logger
        self.clientpool = ClientPool(config_dict, config_save_path, logger)
        # 设置最大并发量
        self.semaphore = asyncio.Semaphore(config_dict["semaphore"])
        self.logger.info("初始化完成!")
        # _, js = self.loop.run_until_complete(asyncio.ensure_future(self.clientpool.send_get_request('https://www.pixiv.net/ajax/user/25170019/profile/all?lang=zh&version=54b602d334dbd7fa098ee5301611eda1776f6f39', '1')))
        # print(js)
        # exit(0)

    def run(self):
        """try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)"""
        newtime = time.strftime("%Y%m%d%H%M%S")
        
        if compare_datetime(
            self.config_dict["last_record_time"], newtime
        ):
            # 获取关注的作者
            if self.ifstop:
                self.loop.stop()
                return
            self.followings_recorder = FollowingsRecorder(
                self.clientpool.myclient, self.asyncdb, self.logger,self.semaphore    # , self.progress_signal
            )
            self.followings_recorder.set_version(self.version)
            # success = self.loop.run_until_complete(asyncio.ensure_future(
            #     self.followings_recorder.bookmarked_work_fetcher()))
            '''
            success = self.loop.run_until_complete(asyncio.ensure_future(
                self.followings_recorder.following_work_fetcher()))
            # success = await self.followings_recorder.following_work_fetcher()
            if not success:
                # self.break_signal.emit()
                self.loop.stop()
                exit(0) 
                return'''
            del self.followings_recorder
            # 获取关注的作者的信息
            if self.ifstop:
                self.loop.stop()
                return
            self.info_getter = WorkInfoRecorder(
                self.clientpool,
                self.config_dict["download_type"],
                self.asyncdb,
                self.asyncbackup_collection,
                self.logger,
                self.semaphore
            )
            self.info_getter.set_version(self.version)
            success = self.loop.run_until_complete(asyncio.ensure_future(
                self.info_getter.start_get_info()))
            # success = await self.info_getter.start_get_info()
            if success:
                self.config_dict.update({"last_record_time": newtime})
                ConfigSetter.set_config(
                    self.config_save_path, self.config_dict)
            del self.info_getter
        else:
            self.logger.info("最近已获取,跳过")
        exit(0)
        # 下载作品
        if self.ifstop:
            self.loop.stop()
            exit(0)
            return
        self.downloader = DownloaderHttpx(
            self.config_dict["save_path"],
            self.clientpool,
            self.config_dict["download_type"],
            self.semaphore,
            self.asyncbackup_collection,
            self.logger,
        )
        loop.run_until_complete(asyncio.ensure_future(
            self.downloader.start_following_download()))
        # await self.downloader.start_following_download()
        del self.downloader
        
        # self.break_signal.emit()
        self.loop.stop()
        exit(0)

    def stop(self):
        self.ifstop = True
        try:
            self.followings_recorder.stop_recording()
        except AttributeError:
            pass
        try:
            self.info_getter.stop_getting()
        except AttributeError:
            pass
        try:
            self.downloader.stop_downloading()
        except AttributeError:
            pass
        return 0


def terminate_signal_handler(signal, frame):
    logger.info("手动终止程序,正在停止......")
    manager.stop()
    sys.exit(0)


if __name__ == "__main__":
    # 日志
    logging.basicConfig(
        format="%(asctime)s => [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        level=logging.INFO)
    logger = logging.getLogger('basic_logger')
    # logger.propagate = False
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(logging.DEBUG)

    # logger = logging.Logger("pixiv")
    # logger.init(True)

    # ====================================
    logger.info("开始初始化程序......")

    # 初始化设置信息
    logger.info("读取配置文件......")
    app_path = os.path.dirname(__file__)
    default_config_save_path = os.path.join(os.path.abspath(app_path), "default_config.json")
    config_save_path = os.path.join(os.path.abspath(app_path), "config.json")
    config_dict = ConfigSetter.get_config(config_save_path, default_config_save_path)
    
    # 初始化协程事件循环
    logger.info("初始化协程事件循环......")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 初始化数据库
    logger.info("初始化数据库......")
    asyncclient = motor_asyncio.AsyncIOMotorClient('localhost', 27017, io_loop=loop)
    asyncdb = asyncclient["pixiv"]
    asyncbackupcollection = asyncclient["backup"]["backup of pixiv infos"]

    # 实例化爬虫管理类
    manager = AsyncThreadingManager(config_dict, config_save_path, loop, asyncdb,
                                         asyncbackupcollection, logger)
    
    # 终止信号处理
    signal.signal(signal.SIGINT, terminate_signal_handler)
    signal.signal(signal.SIGTERM, terminate_signal_handler)
    
    # 启动爬虫
    manager.run()
    # future = asyncio.ensure_future(manager.run())
    # cl.add_client("pixiv_webcrawler_1@proton.me", "pixiv_webcrawler")
    # cl.add_client("pweb2@tutamail.com", "pixiv_webcrawler")
    # cl.add_client("pwebc3@outlook.com", "pixiv_webcrawler")
    
    # 等待程序结束/终止信号
    while True:
        time.sleep(1)
