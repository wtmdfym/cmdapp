import asyncio
from data import Request, Response, SpiderResult
from middlewares import BaseMiddleware, RetryRequest
from pipelines import BasePipeline


class BaseSpider:

    name = "base"
    middlewares: list[BaseMiddleware] = [RetryRequest()]
    pipelines: list[BasePipeline] = [BasePipeline()]

    def __init__(self, logger):
        self.logger = logger
        self.init_requesets = [
            Request("GET", "https://example.com", callback=self.parse)
        ]

        self.is_start = False
        self._futures: list[asyncio.Future] = []

    def start(self) -> list[Request]:
        self.logger.info("Spider %s start." % self.name)
        self.is_start = True
        return self.init_requesets

    def add_future_res(self, future_response: asyncio.Future):
        self._futures.append(future_response)

    def try_parse_future(self):
        for _future in self._futures:
            if _future.done():
                self._futures.remove(_future)
                yield self.parse(_future.result())

    def parse(self, response: Response) -> SpiderResult:
        return SpiderResult(raw_data=response.text())
