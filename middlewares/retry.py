from .base import BaseMiddleware


class RetryRequest(BaseMiddleware):

    def process_response(self, response):
        if response.ok:
            return response
        request = response.request
        if request.retry_times < request.max_retry:
            request = request.next_retry()
        else:
            if request.priority == 100:
                # ignore this request
                return response

            # retry at last
            request.retry_times = 0
            request.priority = 100

        return request
