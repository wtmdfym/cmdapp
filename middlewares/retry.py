from data.models import Request
from .base import BaseMiddleware


class RetryRequest(BaseMiddleware):
    def process_request(self, request: Request) -> Request | None:

        if request.retry_times >= request.max_retry:
            if request.priority == 100:
                # ignore this request
                request.ignore()

            # Perform a final retry with the lowest priority.
            request.retry_times = 0
            request.priority = 100

        if request._ignore:
            return None

        return request

    def process_response(self, response):
        if response.ok:
            return response

        request = response.request
        if request.retry_times < request.max_retry:
            request = request.next_retry()

        return request
