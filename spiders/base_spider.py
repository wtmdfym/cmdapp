from data import Request, Response, SpiderResult, Item
from middlewares import BaseMiddleware, RetryRequest


class BaseSpider:

    name = "base"
    middlewares: list[BaseMiddleware] = [RetryRequest()]
    registry: dict[str, str] = {"print": "base"}

    def __init__(self, logger, **kwargs):
        self.logger = logger
        self.init_requests = [
            Request("GET", "https://example.com", spider_parser=self.parse)
        ]

        self.is_start = False

    def start(self) -> list[Request]:
        self.logger.info("Spider %s start." % self.name)
        self.is_start = True
        return self.init_requests

    async def parse(self, response: Response):
        return SpiderResult(
            items=[
                Item(
                    type="print",
                    data={"data": response.text()},
                )
            ],
        )
