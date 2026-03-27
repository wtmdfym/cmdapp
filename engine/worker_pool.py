import asyncio
from enum import Enum
from data import Request, Response, ParseError


class WorkerStatus(Enum):
    WAITING = "waiting"
    RUNNING = "running"


class WorkerPool:
    def __init__(
        self,
        logger,
        shutdown_event: asyncio.Event,
        scheduler,
        downloader,
        middleware,
        pipeline_manager,
        worker_count: int = 5,
    ) -> None:
        self.logger = logger
        self.shutdown_event = shutdown_event
        self.scheduler = scheduler
        self.downloader = downloader
        self.middleware = middleware
        self.pipeline_manager = pipeline_manager

        self.worker_status: dict[str, WorkerStatus] = {}

        self.worker_count = worker_count
        self._workers: set[asyncio.Task] = set()

    async def start_workers(self):
        r"""TODO restart
        2026-03-26 23:49:29 [ERROR] - crawler - c:\Users\Administrator\Desktop\pixiv-crawler\cmdapp\engine\worker_pool.py:59 - [_on_worker_done] - Unhandled exceptions in Task: worker-0
            Traceback (most recent call last):
            File "c:\Users\Administrator\Desktop\pixiv-crawler\cmdapp\engine\worker_pool.py", line 109, in worker_loop
                spider_result = await request.spider_parser(result)
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            File "c:\Users\Administrator\Desktop\pixiv-crawler\cmdapp\spiders\pixiv\tools.py", line 111, in parse_image_links
                await dataservice.record_in_user(info),
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            File "c:\Users\Administrator\Desktop\pixiv-crawler\cmdapp\storage\data_service.py", line 101, in record_in_user
                raise Exception(f"Database Error, user not find. User name: {user_name}")
            Exception: Database Error, user not find. User name: yt_云天月千雪
        """
        for i in range(self.worker_count):
            name = f"worker-{i}"
            task = asyncio.create_task(self.worker_loop(name), name=name)
            task.add_done_callback(self._on_worker_done)
            self.worker_status[name] = WorkerStatus.RUNNING
            self._workers.add(task)

    def shutdown(self):
        self.shutdown_event.set()

    def _on_worker_done(self, worker):
        self.worker_status.pop(worker.get_name())
        self._workers.discard(worker)

        if worker.cancelled():
            return

        exc = worker.exception()
        if exc is None:
            return

        if isinstance(exc, asyncio.QueueShutDown):
            return

        self.logger.exception(
            f"Unhandled exceptions in Task: {worker.get_name()}", exc_info=exc
        )

    @property
    def is_running(self) -> bool:
        for status in self.worker_status.values():
            if status == WorkerStatus.RUNNING:
                return True

        return False

    async def worker_loop(self, name):
        self.logger.info(f"Worker start: {name}")

        while not self.shutdown_event.is_set():

            self.worker_status[name] = WorkerStatus.WAITING
            request = await self.scheduler.get()

            self.worker_status[name] = WorkerStatus.RUNNING
            fp = request.fingerprint.hex()
            try:
                self.logger.debug(f"Wait for response: {fp}")
                result = await self.downloader.submit(request)
                result = await self.handle_response(result)
            except Exception as e:
                result = self.middleware.process_exception(request, e)
                # Failed request handled by middleware; log error if no recovery
                if result is None:
                    self.logger.error(
                        f"Request failed and discarded: {request.url} (fingerprint={fp})",
                        exc_info=e,
                    )
                    continue

            if isinstance(result, Request):
                await self.handle_request(result)
                continue

            if result is None:
                # Response handling failed
                self.logger.warning(
                    f"Response handling failed for: {request.url} (fingerprint={fp})"
                )
                continue

            # Request success
            self.logger.debug(f"Call spider_callback: {fp}")
            try:
                spider_result = await request.spider_parser(result)
                # parse success -> don't need request again
                self.scheduler.mark_done(request.fingerprint)
            except ParseError as e:
                self.logger.critical(
                    "Spider parse failed. Parse method need update.",
                    exc_info=e,
                )
                self.shutdown()
                return

            success = await self.pipeline_manager.process(
                spider_result.items,
            )

            await self.scheduler.submit_requests(spider_result.requests)

        self.logger.info(f"Worker stop: {name}")

    async def handle_response(self, response: Response) -> Response | None:

        result = self.middleware.process_response(response)

        if isinstance(result, Response):
            return result

        if not await self.handle_request(result):
            # Invalid request returned from middleware; unable to schedule
            self.logger.warning(
                f"Invalid request generated: {result} (URL: {getattr(result, 'url', 'N/A')})"
            )
        return None

    async def handle_request(self, request: Request):
        new_request = self.middleware.process_request(request)
        if new_request is None:
            return False
        return await self.scheduler.submit(new_request)
