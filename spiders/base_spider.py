from data import Request, Response, SpiderStatus, SpiderResult, PrintItem
from middlewares import BaseMiddleware, RetryRequest


class BaseSpider:
    """
    Endpoint requests must have higher priority to prevent the number of requests from growing too quickly.
    """

    name = "base"
    middlewares: list[type[BaseMiddleware]] = [RetryRequest]
    registry: dict[str, str] = {"print": "base"}

    status = SpiderStatus.WAIT

    def __init__(self, logger, **kwargs):
        self.logger = logger
        self.init_requests = [
            Request("GET", "https://example.com", spider_parser=self.parse)
        ]

    async def start(self) -> list[Request]:
        self.logger.info("Spider %s start." % self.name)
        self.status = SpiderStatus.RUNNING
        return self.init_requests

    async def parse(self, response: Response):
        return SpiderResult(
            items=[PrintItem(data={"data": response.text()})],
        )


class SpiderCollection:
    # TODO 合并
    name = "base"
    _spiders: set[type[BaseSpider]] = set()

    def __init__(self, logger) -> None:
        self.logger = logger
        self.index: int = 0
        self.spiders: list[BaseSpider] = []

    def initialize(self, **kwargs):
        for Spider in self._spiders:
            self.spiders.append(Spider(self.logger, **kwargs))

    def add_spider(self, spider: type[BaseSpider], **kwargs):
        self.spiders.append(spider(self.logger, **kwargs))

    def get_spider(self):
        if self.index < len(self.spiders):
            spider = self.spiders[self.index]
            self.index += 1

        else:
            self.index = 0
            spider = self.spiders[self.index]

        return spider

    def list_spider_with_status(self):
        for spider in self.spiders:
            yield f"    {spider.status.name} {spider.name:<30}"

    def pop_spider(self):
        if self.spiders:
            return self.spiders.pop()
