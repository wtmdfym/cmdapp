import sys
from pathlib import Path
import asyncio
import logging.config
from collections import deque

# Add project root path to Python PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import Request, Response, EngineStatus
from utils import *
from spiders import *
from scheduler import Scheduler
from downloader import *
from middlewares import *
from pipelines import PipelineManager


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
        self.scheduler = Scheduler()
        self.downloader = Downloader(client_pool=self.client_pool)
        self.middleware = MiddlewareManager(self.logger)
        self.pipeline = PipelineManager()

        self.status = EngineStatus.STOP
        self._spiders: list[BaseSpider] = []
        self._requests: deque[Request] = deque()
        self._tasks: set[asyncio.Task] = set()
        self.running_spider: BaseSpider | None = None

    async def start(self):
        try:
            await self.client_pool.initialize()
            self.status = EngineStatus.RUNNING
        except RuntimeError as e:
            self.logger.exception(e)
            await self.stop()
        finally:
            if not self.status == EngineStatus.RUNNING:
                raise RuntimeError("Engine start failed!")

    def pause(self):
        self.status = EngineStatus.PAUSE
        self.downloader.pause()

    def resume(self):
        self.downloader.resume()
        self.status = EngineStatus.RUNNING

    async def stop(self):
        self.pause()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        await self.scheduler.shutdown()
        await self.client_pool.shutdown()
        self.status = EngineStatus.STOP
        self.downloader.resume()

    def run_task(self, task: asyncio.Task):
        self._tasks.add(task)

        def done(finished_task):
            try:
                finished_task.result()
            except Exception as e:
                self.logger.exception(e)
            self._tasks.discard(finished_task)

        task.add_done_callback(done)

    def add_spider(self, spider: BaseSpider):
        self._spiders.append(spider)

    def run_spider(self, name: str):
        """
        Only one spider program can be run at a time.
        """
        if len(self._spiders) == 0:
            return

        if self.running_spider:
            self.logger.warning(
                "Spider %s is already running." % self.running_spider.name
            )
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
        self._requests.extend(spider.start())
        self.middleware.set_middlewares(spider.middlewares)
        self.pipeline.add_pipelines(spider.pipelines)

        # Resume main loop
        if self.status == EngineStatus.PAUSE:
            self.resume()

    async def run(self):

        while self.status != EngineStatus.STOP:

            # Pause point 1
            while self.status == EngineStatus.PAUSE:
                self.logger.debug("The engine has been paused and is awaiting resume.")
                if self.status == EngineStatus.STOP:
                    return
                await asyncio.sleep(0.1)

            # Exit
            if (
                len(self._requests) == 0
                and self.scheduler.empty
                and len(self._tasks) == 0
                or self.running_spider is None
            ):
                if self.running_spider:
                    self.logger.info("Spider %s finished." % self.running_spider.name)
                    self.running_spider = None
                self.pause()
                continue

            # avoid block
            if len(self._requests) > 0:
                if not self.scheduler.blocked:
                    _request = self._requests.popleft()
                    success = self.scheduler.submit(_request)
                    if success:
                        self.logger.info("Schedule request: %s" % _request.url)
                    else:
                        self.logger.warning(
                            "The target URL for this request has been scheduled for execution."
                        )

            _request = self.scheduler.get()
            _request = self.middleware.process_request(_request)

            if _request is None:
                continue

            # add hooks
            if _request.errback is None:
                _request.errback = self.middleware.process_exception

            # Scheduler queue has pending request
            _future = asyncio.get_running_loop().create_future()

            response_task = self.downloader.submit(_request, _future)
            # Pause point 2
            self.run_task(response_task)

            _future.add_done_callback(
                lambda f, request=_request: self.request_callback(request, f)
            )

            await asyncio.sleep(0.1)

    async def request_callback(
        self,
        request: Request,
        future: asyncio.Future,
    ):
        try:
            response = future.result()
            result = self.middleware.process_response(response)
        except Exception as e:
            result = self.middleware.process_exception(request, e)
            if result is None:
                self.logger.error("Request failed", e)
                return

            if isinstance(result, Response):
                result = self.middleware.process_response(result)

        if isinstance(result, Request):
            self._requests.append(result)
        else:
            self.scheduler.mark_done(request.fingerprint)
            spider_result = result.request.callback(result)
            self._requests.extend(spider_result.requests)
            success = await self.pipeline.process_item(spider_result)
