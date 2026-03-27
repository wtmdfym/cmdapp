import sys
from pathlib import Path
import asyncio
import logging
from time import time

# Add project root path to Python PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data import EngineStatus, SpiderStatus
from utils import *
from spiders import *
from downloader import *
from middlewares import *
from pipelines import *
from storage import *

from .scheduler import Scheduler
from .worker_pool import WorkerPool


class Engine:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.status = EngineStatus.STOP

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

        self._spider_collections: list[SpiderCollection] = []

        self.shutdown_event = asyncio.Event()
        self.worker_pool = WorkerPool(
            self.logger,
            self.shutdown_event,
            self.scheduler,
            self.downloader,
            self.middleware,
            self.pipeline_manager,
            worker_count=5,
        )

        self.running_spider: BaseSpider | None = None

        self.start_time: float = 0
        self.auto_pause_timer: int = 3

    async def start(self):
        try:
            self.mongo = MongoDBHandler(self.logger, db_name="test")
            self.dataservice = DataService(self.mongo)

            self.pipeline_manager.add_pipeline(BasePipeline())
            self.pipeline_manager.add_pipeline(MongoDBPipeline(self.logger, self.mongo))

            await self.client_pool.initialize()

            self.status = EngineStatus.RUNNING
            await self.worker_pool.start_workers()
            # self.start_workers()
            self.start_time = time()
            self.logger.info("Engine started")
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
        try:
            for w in self.worker_pool._workers.copy():
                w.cancel()
            await asyncio.gather(*self.worker_pool._workers, return_exceptions=True)
        except Exception:
            pass

        await self.scheduler.shutdown()
        await self.client_pool.shutdown()
        await self.mongo.close()

        self.status = EngineStatus.STOP
        self.downloader.resume()
        self.shutdown_event.clear()
        self.logger.info("Engine Shutdown")

    def get_status(self):
        seconds = time() - self.start_time
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return {
            "status": self.status.value,
            "running_time": f"{hours:02d}:{minutes:02d}:{secs:02d}",
            "running_spider": self.running_spider.name if self.running_spider else None,
            "worker_count": len(self.worker_pool._workers),
            "queue_size": self.scheduler.size,
            "finished_requests": self.scheduler.finish_count,
        }

    def add_spider_collection(self, spider_collection: SpiderCollection, **kwargs):
        spider_collection.initialize(**kwargs)
        self._spider_collections.append(spider_collection)

    def run_spider(self, name: str) -> bool:
        """
        Only one spider program can be run in the same time.
        """
        if len(self._spider_collections) == 0:
            return False
        if self.running_spider:
            self.logger.warning("Spider %s is running." % self.running_spider.name)
            return False

        spider = None
        # Get target spider
        for _spider_collection in self._spider_collections:
            for _spider in _spider_collection.spiders:
                if _spider.name == name:
                    spider = _spider
                    break
            if spider:
                break
        if not spider:
            self.logger.warning("Spider %s not found." % name)
            return False

        # Init spider
        if spider.status == "finish":
            self.logger.warning("Spider %s has already been run." % spider.name)
            return False

        self.logger.info("Running spider %s" % spider.name)
        self.running_spider = spider

        self.pipeline_manager.set_routes(spider.registry)
        self.middleware.set_middlewares(spider.middlewares)

        # Resume main loop
        if self.status == EngineStatus.PAUSE:
            self.resume()
        return True

    async def loop(self, will_pause_time: float = 0) -> float:
        # while self.status != EngineStatus.STOP:

        # Pause point 1
        while self.status == EngineStatus.PAUSE:
            if self.status == EngineStatus.STOP:
                return will_pause_time
            await asyncio.sleep(1)

        # Init spider
        if self.running_spider:
            if self.running_spider.status != SpiderStatus.RUNNING:
                await self.scheduler.submit_requests(await self.running_spider.start())

        if self.running_spider is None or (
            self.scheduler.empty and not self.worker_pool.is_running
        ):

            # Pause after delay
            time_now = time()
            if will_pause_time == 0:
                will_pause_time = time()
            if time_now - will_pause_time < self.auto_pause_timer:
                # continue
                return will_pause_time

            if self.running_spider:
                self.logger.info(f"Spider {self.running_spider.name} finished.")
                self.running_spider.status = SpiderStatus.FINISH
                self.running_spider = None
            will_pause_time = 0
            self.pause()
            # continue
            return will_pause_time

        # await self.run_scheduled_request()
        if self.shutdown_event.is_set():
            asyncio.create_task(self.shutdown())

        self.logger.debug("Complete one main loop cycle.")
        await asyncio.sleep(0.5)
        return will_pause_time
