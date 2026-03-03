# -*-coding:utf-8-*-
import asyncio, time
import logging
import logging.config
import sys
import signal
import os
from threading import Thread

from info_recorders import FollowingsRecorder, WorkIdFetcher, work_info_recorder
from download_hander import DownloadHander
from common import ConfigHander, MyLogger, ClientPool, MongoDBHander, compare_datetime

LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "detail",
            "stream": "ext://sys.stdout",
        },
        "detail": {
            "class": "logging.StreamHandler",
            "formatter": "detail",
            "stream": "ext://sys.stdout",
        },
        "simple": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
    },
    "formatters": {
        "detail": {
            "format": "%(levelname)s [%(asctime)s] [%(funcName)s] - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(levelname)s [%(asctime)s] - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "loggers": {
        "main": {
            "handlers": ["detail"],
            "level": "INFO",
        },
        "httpx": {
            "handlers": ["simple"],
            "level": "INFO",
        },
        "httpcore": {
            "handlers": ["simple"],
            "level": "INFO",
        },
    },
}


def main() -> None:
    # Loggings
    logging.config.dictConfig(LOGGING_CONFIG)
    # logger = MyLogger(test="fsf")
    logger = logging.getLogger("main")

    # logger.propagate = False

    # ====================================
    logger.info("Initialize application......")

    # 初始化设置信息
    logger.info("Load config file......")
    app_path = os.path.dirname(__file__)
    default_config_save_path = os.path.join(
        os.path.abspath(app_path), "default_config.json"
    )
    config_save_path = os.path.join(os.path.abspath(app_path), "webCrawler_config.json")
    config_hander = ConfigHander(config_save_path, default_config_save_path)

    # 初始化协程事件循环
    logger.info("Initialize event loop......")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mongoDb_hander = MongoDBHander(logger=logger, loop=loop)
    # TODO add to config file
    clientpool = ClientPool(config_hander, logger, pause_time=0.6)
    logger.info("Initialize application complete.")

    # clientpool.add_client("pixiv_webcrawler_1@proton.me", "pixiv_webcrawler")
    # clientpool.add_client("pweb2@tutamail.com", "pixiv_webcrawler")
    # clientpool.add_client("pwebc3@outlook.com", "pixiv_webcrawler")
    # config_hander.save_config()
    newtime = time.strftime("%Y%m%d%H%M%S")
    if compare_datetime(config_hander.require_config("last_record_time"), newtime):
        followings_recorder = FollowingsRecorder(
            clientpool,
            mongoDb_hander,
            logger,
            myId="83945559",
        )
        res = loop.run_until_complete(
            asyncio.ensure_future(followings_recorder.start())
        )
        if not res:
            return
        work_id_fether = WorkIdFetcher(
            config_hander,
            clientpool,
            mongoDb_hander,
            logger,
            # myId="83945559",
        )
        res = loop.run_until_complete(asyncio.ensure_future(work_id_fether.start()))
        if not res:
            return
        config_hander.update_config("last_record_time", newtime)
        config_hander.save_config()
    else:
        logger.info("Recently fecthed, skip fetch info.")
    download_hander = DownloadHander(
        config_hander=config_hander,
        clientpool=clientpool,
        mongoDb_hander=mongoDb_hander,
        logger=logger,
    )
    res = loop.run_until_complete(asyncio.ensure_future(download_hander.start()))
    # loop.run_until_complete(
    #     asyncio.ensure_future(
    #         test_work_info_recorder(clientpool, logger, mongoDb_hander)
    #     )
    # )


async def test_work_info_recorder(
    clientpool: ClientPool, logger: logging.Logger, mongoDb_hander: MongoDBHander
):
    from typing import Literal

    logger.setLevel(level=logging.DEBUG)
    w = work_info_recorder.WorkInfoRecorder(
        clientpool,
        logger,
        mongoDb_hander,
        asyncio.Semaphore(),
    )
    test_egs: dict[str, Literal["illust", "novel", "series"]] = {
        "120857870": "illust",
        "107715013": "illust",
        "22372987": "novel",
        "156663": "series",
    }
    results: list[bool] = []
    for key, value in test_egs.items():
        res = await w._fetch_info(key, value, False)
        logger.debug(res)
        results.append(res is not None)
    logger.debug(results)


class Manager(Thread):
    def __init__(self) -> None:
        super().__init__(name="spider")
        self.isrunning = True
        self.is_app_initialized = False
        # Loggings
        # logger = MyLogger(name="pixiv")
        # logger.init(True)
        logging.config.dictConfig(LOGGING_CONFIG)
        self.logger = logging.getLogger("main")
        # logger.propagate = False

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.main()
        """
        counter = 0
        while self.isrunning:
            print(counter)
            counter += 1
            time.sleep(1)
        time.sleep(2)"""

    def stop(self) -> None:

        while not self.is_app_initialized:
            time.sleep(0.2)
        self.isrunning = False
        try:
            self.followings_recorder.stop()
        except AttributeError:
            pass
        try:
            self.work_id_fether.stop()
        except AttributeError:
            pass
        try:
            self.download_hander.stop()
        except AttributeError:
            pass
        # self.loop.close()
        self.logger.info("Application stop.")
        sys.stderr.write("[OVER]")
        sys.stderr.flush()
        sys.exit()

    def main(self):

        # ====================================================================
        self.logger.info("Initialize application......")
        self.logger.info("Load config file......")
        app_path = os.path.dirname(__file__)
        default_config_save_path = os.path.join(
            os.path.abspath(app_path), "default_config.json"
        )
        config_save_path = os.path.join(
            os.path.abspath(app_path), "webCrawler_config.json"
        )
        config_hander = ConfigHander(config_save_path, default_config_save_path)

        # 初始化协程事件循环
        self.logger.info("Initialize event loop......")

        mongoDb_hander = MongoDBHander(logger=self.logger, loop=self.loop)
        # TODO add to config file
        clientpool = ClientPool(config_hander, self.logger, pause_time=0.6)
        self.is_app_initialized = True
        self.logger.info("Initialize application complete.")

        # clientpool.add_client("pixiv_webcrawler_1@proton.me", "pixiv_webcrawler")
        # clientpool.add_client("pweb2@tutamail.com", "pixiv_webcrawler")
        # clientpool.add_client("pwebc3@outlook.com", "pixiv_webcrawler")
        # config_hander.save_config()
        # ====================================================================
        newtime = time.strftime("%Y%m%d%H%M%S")
        if compare_datetime(config_hander.require_config("last_record_time"), newtime):
            self.followings_recorder = FollowingsRecorder(
                clientpool,
                mongoDb_hander,
                self.logger,
                myId=config_hander.require_config("myId"),
            )
            res = self.loop.run_until_complete(
                asyncio.ensure_future(self.followings_recorder.start())
            )
            if not res:
                return
            self.work_id_fether = WorkIdFetcher(
                config_hander,
                clientpool,
                mongoDb_hander,
                self.logger,
            )
            res = self.loop.run_until_complete(
                asyncio.ensure_future(self.work_id_fether.start())
            )
            if not res:
                return
            config_hander.update_config("last_record_time", newtime)
            config_hander.save_config()
        else:
            self.logger.info("Recently fecthed, skip fetch info.")
        self.download_hander = DownloadHander(
            config_hander=config_hander,
            clientpool=clientpool,
            mongoDb_hander=mongoDb_hander,
            logger=self.logger,
        )
        res = self.loop.run_until_complete(
            asyncio.ensure_future(self.download_hander.start())
        )
        # loop.run_until_complete(
        #     asyncio.ensure_future(
        #         test_work_info_recorder(clientpool, logger, mongoDb_hander)
        #     )
        # )

    def terminate_signal_handler(self, signal, frame):
        self.logger.info("Manually terminate the program, stopping......")
        self.stop()


if __name__ == "__main__":
    
    """
    # _loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(_loop)
    manager = Manager()
    # 终止信号处理
    signal.signal(signal.SIGINT, manager.terminate_signal_handler)
    signal.signal(signal.SIGTERM, manager.terminate_signal_handler)
    manager.start()
    while manager.is_alive():
        time.sleep(1)"""
    """

    async def read_from_fd(fd: asyncio.StreamReader):
        while True:
            line = await fd.readline()
            if line:
                print(line.strip().decode())
            else:
                break

    async def test():
        stdin_reader = asyncio.StreamReader(loop=_loop)
        stdin_protocol = asyncio.StreamReaderProtocol(stdin_reader, loop=_loop)
        await _loop.connect_read_pipe(lambda: stdin_protocol, sys.stdin)

        stderr_reader = asyncio.StreamReader(loop=_loop)
        stderr_protocol = asyncio.StreamReaderProtocol(stderr_reader, loop=_loop)
        await _loop.connect_read_pipe(lambda: stderr_protocol, sys.stderr)

        # await read_from_fd(stdin_reader)

    _loop.run_until_complete(test())
    """
# C:/Users/Administrator/Desktop/pixiv-crawler/.venv/Scripts/python.exe -m pip list