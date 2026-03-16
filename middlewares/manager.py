from data import Request, Response
from .base import BaseMiddleware


class MiddlewareManager:
    def __init__(self, logger) -> None:
        self.logger = logger
        self.middlewares: list[BaseMiddleware] = []

    def set_middlewares(self, middlewares: list[BaseMiddleware]):
        self.middlewares.clear()
        self.middlewares.extend(
            sorted(
                middlewares,
                key=lambda m: getattr(m, "priority", 500),
            )
        )

    def process_request(self, result: Request | None) -> Request | None:
        for m in self.middlewares:
            if result is not None:
                result = m.process_request(result)  # type: ignore
            else:
                return None

        return result

    def process_response(self, result: Response) -> Request | Response:
        for m in reversed(self.middlewares):
            result = m.process_response(result)  # type: ignore

            if isinstance(result, Request):
                break

        return result

    def process_exception(
        self,
        request: Request,
        exception: Exception,
    ):

        for m in reversed(self.middlewares):

            result = m.process_exception(request, exception)

            if result:
                return result
