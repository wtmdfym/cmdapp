import time
from enum import Enum


class ExecuteResult(Enum):
    SUCCESS = 0
    REQUESTSUCCESS = 1
    REQUESTFAILED = 2
    TOOMANYREQUEST = 3


class RetryStrategy:
    def __init__(self, max_retries: int = 3) -> None:
        # if (priority < 0) or (priority > 100):
        #     raise Exception("Priority out of range!")
        # priority range: 0-100
        # self.priority = priority  # 默认优先级为10，数值越小优先级越高
        self.max_retries = max_retries
        self.childern_strategy = None

    def set_childern_strategy(self, strategy: RetryStrategy):
        self.childern_strategy = strategy

    def should_retry(self, attempt: int, exception) -> bool:
        # 子策略优先级更高
        if self.childern_strategy:
            return self.childern_strategy.should_retry(
                attempt=attempt, exception=exception
            )
        return self.max_retries > attempt

    def get_wait_time(self, attempt: int) -> int:
        return 0

    def should_stop(self, attempt: int) -> bool:
        return False


class DefaultRetryStrategy(RetryStrategy):
    def __init__(self, initial_wait_seconds=0):
        # super().__init__(priority=100)  # 默认策略优先级最低
        super().__init__()
        self.initial_wait_seconds = initial_wait_seconds

    def get_wait_time(self, attempt):
        return self.initial_wait_seconds * (attempt + 1)


class RetryManager:
    def __init__(
        self,
        initial_wait_seconds: int = 1,
    ):
        self.retry = False
        self.initial_wait_seconds = initial_wait_seconds

    def execute_with_retry(self, func, *args, **kwargs):
        attempt = 0
        last_exception = None

        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                retry_code = self._retry_strategy.should_retry(attempt, e)
                if retry_code < 0:
                    break
                if retry_code == 0:
                    retry_code = self.default_strategy.should_retry(attempt, e)
                wait_time = self._retry_strategy.get_wait_time(attempt)
                print(f"Retry [{attempt + 1}], waiting for {wait_time} seconds......")
                time.sleep(wait_time)
                attempt += 1

        # 如果所有重试都失败，抛出最后一次异常
        raise last_exception


"""
class CompositeRetryStrategy(RetryStrategy):
    def __init__(self, strategies: list[RetryStrategy]):
        super().__init__(priority=0)  # 设置CompositeStrategy的优先级最低
        self.strategies = sorted(strategies, key=lambda x: x.priority)

    def should_retry(self, attempt, exception) -> int:
        # 以高优先级策略为准
        for strategy in self.strategies:
            retry_code = strategy.should_retry(attempt, exception)
            if retry_code == 0:
                continue
            else:
                return retry_code
        return 0

    def get_wait_time(self, attempt):
        # 使用所有策略中最大的等待时间
        wait_times = [strategy.get_wait_time(attempt) for strategy in self.strategies]
        return max(wait_times)


class RetryManager:
    def __init__(
        self,
        retry_strategy: RetryStrategy | None = None,
    ):

        self.default_strategy = DefaultRetryStrategy()
        self._retry_strategy = retry_strategy or self.default_strategy

    def set_strategy(self, retry_strategy: RetryStrategy):
        self._retry_strategy = retry_strategy

    def execute_with_retry(self, func, *args, **kwargs):
        attempt = 0
        last_exception = None

        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                retry_code = self._retry_strategy.should_retry(attempt, e)
                if retry_code < 0:
                    break
                if retry_code == 0:
                    retry_code = self.default_strategy.should_retry(attempt, e)
                wait_time = self._retry_strategy.get_wait_time(attempt)
                print(f"Retry [{attempt + 1}], waiting for {wait_time} seconds......")
                time.sleep(wait_time)
                attempt += 1

        # 如果所有重试都失败，抛出最后一次异常
        raise last_exception
"""
