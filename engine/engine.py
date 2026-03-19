import sys
from pathlib import Path
import asyncio
import logging.config
from time import time
from typing import Awaitable

# Add project root path to Python PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import Request, Response, EngineStatus, ParseError
from utils import *
from spiders import *
from .scheduler import Scheduler
from downloader import *
from middlewares import *
from pipelines import *
from storage import MongoDBHandler


class Engine:
    def __init__(self) -> None:
        self.config = ConfigHandler(config_file_path="config.json")
        logging.config.dictConfig(self.config.require("logger_config"))

        # Init all basic compents
        self.logger = logging.getLogger("crawler")
        self.client_pool = ClientPool(
            self.config,
            self.logger,
        )
        self.scheduler = Scheduler(self.logger)
        self.downloader = Downloader(client_pool=self.client_pool)
        self.middleware = MiddlewareManager(self.logger)
        self.pipeline_manager = PipelineManager(self.logger)

        self.mongo = MongoDBHandler(self.logger, db_name="test")
        self.pipeline_manager.add_pipeline(BasePipeline())
        self.pipeline_manager.add_pipeline(MongoDBPipeline(self.logger, self.mongo))

        self.dataservice = DataService(self.mongo)

        self.status = EngineStatus.STOP
        self._spiders: list[BaseSpider] = []

        self._tasks: set[asyncio.Task] = set()
        self._max_task_count = 20
        self._pending_task: asyncio.Task | None = None

        self.running_spider: BaseSpider | None = None

        self.auto_pause_timer: int = 3

    async def start(self):
        try:
            await self.client_pool.initialize()
            self.status = EngineStatus.RUNNING
            self.logger.info("Engine Start")
        except RuntimeError as e:
            self.logger.exception(e)
            await self.shutdown()
        finally:
            if not self.status == EngineStatus.RUNNING:
                raise RuntimeError("Engine start failed!")

    def pause(self):
        self.status = EngineStatus.PAUSE
        self.downloader.pause()
        self.logger.info("Engine Paused")

    def resume(self):
        self.downloader.resume()
        self.status = EngineStatus.RUNNING
        self.logger.info("Engine Resumed")

    async def shutdown(self):
        self.pause()
        for t in self._tasks.copy():
            # TODO RuntimeError（极少但可能）或漏 cancel
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        await self.scheduler.shutdown()
        await self.client_pool.shutdown()
        await self.mongo.close()

        self.status = EngineStatus.STOP
        self.downloader.resume()
        self.logger.info("Engine Shutdown")

    def run_task(self, task: asyncio.Task) -> bool:
        if len(self._tasks) >= self._max_task_count:
            if self._pending_task:
                raise RuntimeError("The pending task have been set.")
            self._pending_task = task
            self.logger.info("Task pending: %s" % task.get_name())
            return False

        self.logger.info("Run task: %s" % task.get_name())
        self._tasks.add(task)

        def done(finished_task):
            try:
                finished_task.result()
            except Exception as e:
                self.logger.exception(e)
            self._tasks.discard(finished_task)

        task.add_done_callback(done)
        return True

    def add_spider(self, spider: type[BaseSpider], **kwargs):
        self._spiders.append(spider(self.logger, **kwargs))

    def set_running_spider(self, name: str):
        """
        Only one spider program can be run in the same time.
        """
        if len(self._spiders) == 0:
            return
        if self.running_spider:
            self.logger.warning("Spider %s is running." % self.running_spider.name)
            return

        spider = None
        # Get target spider
        for _spider in self._spiders:
            if _spider.name == name:
                spider = _spider
                break
        if not spider:
            self.logger.warning("Spider %s not found." % name)
            return

        # Init spider
        if spider.is_start:
            self.logger.warning("Spider %s has already been run." % spider.name)
            return

        self.logger.info("Running spider %s" % spider.name)
        self.running_spider = spider

        self.pipeline_manager.set_routes(spider.registry)
        self.middleware.set_middlewares(spider.middlewares)

        # Resume main loop
        if self.status == EngineStatus.PAUSE:
            self.resume()

    async def loop(self):
        will_pause_time = 0

        while self.status != EngineStatus.STOP:

            # Pause point 1
            while self.status == EngineStatus.PAUSE:
                if self.status == EngineStatus.STOP:
                    return
                await asyncio.sleep(0)

            # Auto Pause
            if (
                self.scheduler.empty and len(self._tasks) == 0
            ) or self.running_spider is None:
                # Init spider
                if self.running_spider:
                    if not self.running_spider.is_start:
                        await self.scheduler.submit_requests(
                            self.running_spider.start()
                        )

                # Pause after delay
                time_now = time()
                if will_pause_time == 0:
                    will_pause_time = time()
                if time_now - will_pause_time < self.auto_pause_timer:
                    continue

                if self.running_spider:
                    self.logger.info(f"Spider {self.running_spider.name} finished.")
                    self.running_spider = None
                will_pause_time = 0
                self.pause()
                continue

            await self.run_scheduled_request()

            self.logger.debug("Complete one main loop cycle.")
            await asyncio.sleep(0)

    async def run_scheduled_request(self):
        if self._pending_task:
            # Limit running tasks count
            if self.run_task(self._pending_task):
                # Reset
                self._pending_task = None

        _request = self.scheduler.get_nowait()
        if _request is None:
            # Release resources and avoid being unable to exit due to indefinite waiting.
            await asyncio.sleep(1)
            return

        _request = self.middleware.process_request(_request)
        if _request is None:
            return

        self.logger.debug("Submit request: %s" % _request.fingerprint)

        # add hooks
        if _request.errback is None:
            _request.errback = self.middleware.process_exception

        response_task = self.downloader.submit(_request)
        # Pause point 2
        response_task = asyncio.create_task(
            self.request_callback(_request, response_task),
            name=_request.fingerprint.hex(),
        )
        self.run_task(response_task)

    async def request_callback(
        self,
        request: Request,
        result_task: Awaitable,
        # future: asyncio.Future[Response | Request],
    ):
        fp = request.fingerprint
        self.logger.debug("Callback called: %s" % fp.hex())
        try:
            result = await result_task
        except Exception as e:
            result = self.middleware.process_exception(request, e)
            # TODO failed requeset
            if result is None:
                self.logger.error("Request failed", e)
                return

        if isinstance(result, Request):
            await self.handle_request(result)
            return

        result = await self.handle_response(result)
        if result is None:
            # TODO failed requeset
            return

        # Request success
        self.logger.debug("Call spider_callback: %s" % fp.hex())
        try:
            spider_result = await result.request.spider_parser(result)
            # parse success -> don't need request again
            self.scheduler.mark_done(fp)
        except ParseError as e:
            self.logger.critical(
                "Spider parse failed. Parse method need update.",
                exc_info=e,
            )
            asyncio.create_task(self.shutdown())
            return

        success = await self.pipeline_manager.process(
            spider_result.items,
        )

        await self.scheduler.submit_requests(spider_result.requests)

    async def handle_response(self, response: Response) -> Response | None:

        result = self.middleware.process_response(response)

        if isinstance(result, Response):
            return result

        if not await self.handle_request(result):
            # TODO Wrong request generater
            pass
        return None

    async def handle_request(self, resquest: Request):
        new_request = self.middleware.process_request(resquest)
        if new_request is None:
            return
        return await self.scheduler.submit(new_request)
