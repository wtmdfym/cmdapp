# -*-coding:utf-8-*-
import asyncio, time
import logging
import logging.config
import sys
import signal
import os

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
    # logger = MyLogger(name="pixiv")
    # logger.init(True)
    logging.config.dictConfig(LOGGING_CONFIG)
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
            myId="83945559",
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
    w = work_info_recorder.WorkInfoRecorder(clientpool, logger, mongoDb_hander)
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


if __name__ == "__main__":
    main()

"""
    # 实例化爬虫管理类
    manager = AsyncThreadingManager(config_hander, config_save_path, loop, logger)

    # 终止信号处理
    signal.signal(signal.SIGINT, terminate_signal_handler)
    signal.signal(signal.SIGTERM, terminate_signal_handler)

    # 启动爬虫
    manager.run()
    # future = asyncio.ensure_future(manager.run())
    # 

    # 等待程序结束/终止信号
    while True:
        time.sleep(1)
    
        ,
        {
            "email": "pixiv_webcrawler_1@proton.me",
            "passward": "pixiv_webcrawler",
            "cookies": {
                "PHPSESSID": "107676858_uQ45bDxg7Kd4N25c1N48d94RaFh4DwR9"
            }
        },
        {
            "email": "pweb2@tutamail.com",
            "passward": "pixiv_webcrawler",
            "cookies": {
                "PHPSESSID": "107703613_SzkNLjJyufu91ItXCaBEQgVgKpbkqaRX"
            }
        }
"""
