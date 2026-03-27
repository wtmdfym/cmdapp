from data.models import Request
from .base import BaseMiddleware


class RetryRequest(BaseMiddleware):
    priority = 400

    def process_request(self, request: Request) -> Request | None:

        if request.retry_times >= request.max_retry:
            if request.priority == 100:
                # ignore this request
                request.ignore = True

            # Perform a final retry with the lowest priority.
            self.logger.info(
                f"Set the request to lowest priority and retry: {request.fingerprint}"
            )
            request.retry_times = 0
            request.priority = 100

        if request.ignore:
            self.logger.warning(f"All retries failed, ignore: {request.fingerprint}")
            return None

        return request

    def process_response(self, response):
        if response.ok:
            return response

        request = response.request
        if request.retry_times < request.max_retry:
            self.logger.info(f"Retry request: {request.fingerprint}")
            request = request.next_retry()
        else:
            self.logger.warning(f"Request reach max retry: {request.fingerprint}")
        return request
