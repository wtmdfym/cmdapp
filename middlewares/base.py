from data import Request, Response


class BaseMiddleware:
    priority = 500  # 0 - 1000

    def __init__(self) -> None:
        pass

    def process_request(self, request: Request) -> Request | None:
        # Only allow change request fileds
        return request

    def process_response(self, response: Response) -> Request | Response:
        return response

    def process_exception(
        self,
        request: Request,
        e: Exception,
    ) -> Request | Response | None:
        return request
