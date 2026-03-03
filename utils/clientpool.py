import httpx
import random
import time
import asyncio
from logging import Logger
from common import ConfigHander, ResponseHander, format_cookie
from utils.retry import *


class ClientPool:
    """
    __headers: The headers when sending a HTTP request to pixiv
    version: Parameters in the Pixiv request link (usefulness unknown)
    cookies: The cookies when a request is sent to pixiv
    """

    _headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
        "referer": "https://www.pixiv.net/",
    }

    def __init__(
        self, config_hander: ConfigHander, logger: Logger, pause_time: float
    ) -> None:
        logger.info("Initialize client pool......")
        self.config_hander = config_hander
        self.logger = logger
        # pause to avoid being forbidden by pixiv server
        self.pause_time = pause_time

        # Load pool info
        self.client_pool_info: list[dict] = []
        saved_pool_info = self.config_hander.get_config("client_pool")
        assert isinstance(saved_pool_info, list)
        self.client_pool_info.extend(saved_pool_info)
        self.client_pool: list[httpx.AsyncClient] = []
        self.added_account = []
        self.isreloading = False

        # ============Initialize httpx client config============
        self.version = "54b602d334dbd7fa098ee5301611eda1776f6f39"
        self.timeout = httpx.Timeout(8.0, connect=10.0, read=25.0)
        semaphore = self.config_hander.get_config("semaphore")
        limits = httpx.Limits(
            max_keepalive_connections=semaphore, max_connections=semaphore
        )

        # proxy
        http_proxy = None
        https_proxy = None
        if config_hander.require_config("enable_proxy"):
            http_proxy = httpx.Proxy(url=config_hander.require_config("http_proxies"))
            https_proxy = httpx.Proxy(url=config_hander.require_config("https_proxies"))
        self.mounts = {
            "http://": httpx.AsyncHTTPTransport(
                proxy=http_proxy, limits=limits, retries=3
            ),
            "https://": httpx.AsyncHTTPTransport(
                proxy=https_proxy,
                limits=limits,
                retries=3,
            ),
        }
        # retry
        self.retry_manager = RetryManager()
        """self.common_strategies = [
            RequestErrorRetryStrategy(max_retries=3),
            ServerBusyRetryStrategy(max_retries=1),
        ]"""

        self.creat_my_client()
        self.creat_pool()

    @property
    def headers(self):
        return self._headers

    def creat_my_client(self) -> None:
        self.logger.debug("Creat client------my account")
        cookies = self.config_hander.get_config("cookies")
        assert isinstance(cookies, dict)
        if self.test_client(cookies):
            self.myclient = httpx.AsyncClient(
                headers=self._headers,
                cookies=cookies,
                timeout=self.timeout,
                mounts=self.mounts,
            )
            self.logger.debug("success")
        else:
            self.logger.warning("Cookies error------my account")

    def creat_pool(self) -> bool:
        if self.client_pool_info is not None:
            for client_info in self.client_pool_info:
                self.added_account.append(client_info.get("email"))
                client = self.creat_client(client_info)
                if client is not None:
                    self.client_pool.append(client)
        else:
            self.logger.warning("未添加pixiv连接池账号, 将使用个人账号!")
            self.client_pool.append(self.myclient)
        if len(self.client_pool) == 0:
            self.logger.warning("无任何可用账号,连接池启动失败!")
            return False
        else:
            self.logger.info("Client pool started.")
            return True

    def add_client(self, email: str, passward: str) -> bool:
        if email in self.added_account:
            update_cookie = input("Pixiv账号已记录,是否更新Cookies?(y/n)")
            if update_cookie == ("n" or "N"):
                return False
            else:
                for client_info in self.client_pool_info:
                    if client_info.get("email") == email:
                        self.client_pool_info.remove(client_info)
                self.reload_pool()
        # 自动获取新账号的cookie
        # TODO
        # 手动输入
        oringal_cookies = input("输入你Pixiv账号的Cookies:")
        cookies = format_cookie(oringal_cookies)
        # 检查Cookie是否正确
        assert cookies.get(
            "PHPSESSID"
        ), f"Cookies错误!------Account email: {email}\nCookies: {cookies}"
        # Test client
        self.logger.info("Testing......")
        if self.test_client(cookies):
            # Update config file
            client_info = {"email": email, "passward": passward, "cookies": cookies}
            self.client_pool_info.append(client_info)
            self.config_hander.update_config("client_pool", self.client_pool_info)
            self.logger.info("账号添加成功!")
            return True
        else:
            self.logger.warning("账号添加失败------该账号无法访问pixiv个人主页!")
            return False

    def creat_client(self, client_info: dict) -> httpx.AsyncClient | None:
        self.logger.debug(f"Creat client------email:{client_info.get('email')}")
        cookies = client_info.get("cookies")
        assert isinstance(cookies, dict)

        if self.test_client(cookies):
            client = httpx.AsyncClient(
                headers=self._headers,
                cookies=cookies,
                timeout=self.timeout,
                mounts=self.mounts,
            )
            self.logger.debug("Creat client success.")
            return client
        else:
            self.logger.warning(
                f"Cookies error, need update!------Account email: {client_info.get('email')}"
            )

    def test_client(self, cookies: dict[str, str]) -> bool:
        # TODO 修改
        self.logger.debug("Testing......")
        client = httpx.Client(
            headers=self._headers,
            cookies=cookies,
            timeout=self.timeout,
            mounts={
                "http://": httpx.HTTPTransport(
                    proxy=self.config_hander.get_config("http_proxies"),
                ),
                "https://": httpx.HTTPTransport(
                    proxy=self.config_hander.get_config("https_proxies"),
                ),
            },
        )
        res = client.get("https://www.pixiv.net/settings/account")
        if res.status_code == 200:
            return True
        elif res.status_code == 302:
            return False
        else:
            raise Exception(f"Unkonwn status_code:{res.status_code}")

    def reload_pool(self):
        if self.isreloading:
            return
        self.isreloading = True
        self.logger.info("Reload client pool......")
        self.client_pool.clear()
        self.creat_pool()
        self.isreloading = False

    """
    async def get(
        self,
        url: str,
        params: list[tuple] = [],
        headers: dict | None = None,
        use_myclient: bool = False,
        retry_strategies: list[RetryStrategy] | None = None,
    ) -> ResponseHander:
        # params.append(("version", self.version))  not necessary
        while self.isreloading:
            time.sleep(0.5)
        if use_myclient:
            client = self.myclient
        else:
            client = random.choice(self.client_pool)

        if retry_strategies:
            retry_strategies.extend(self.common_strategies)

            self.retry_manager.set_strategy(
                CompositeRetryStrategy(retry_strategies)
            )
        else:
            self.retry_manager.set_strategy(
                CompositeRetryStrategy(self.common_strategies)
            )

        response = await self.retry_manager.execute_with_retry(
            lambda: client.get(url, headers=headers, params=params)
        )
        time.sleep(self.pause_time)
        if response.is_success:
            response_hander.set_response(response)
            if response_hander.check():
                break
            if isretry:
                self.logger.info("Auto retry failed.")
                response_hander.res_code = 1
                break
            else:
                isretry = True
                continue
            return response_hander
        else:
            if response.status_code == 401:
                self.logger.critical("Cookies Error, check and reset cookies.")
            elif response.status_code == 403:
                self.logger.warning("Access Forbidden")
            elif response.status_code == 404:
                self.logger.warning("Not Found or Hiden by User")
            elif response.status_code == 429:
                self.logger.warning(
                    "Too Many Reautes!\nThere may be a risk of being blocked, the program will\
                        be automatically stopped.\nSuggest reduce semaphore or add pause time."
                )
            else:
                self.logger.warning(
                    f"Unhandled Status Code: {response.status_code}"
                )
            raise RequestNotSuccess(response=response)
        httpx.ConnectError:
            self.logger.warning("Proxy Error, auto pause 5s, check your proxy!")
            time.sleep(5)
            self.reload_pool()
            isretry = True
            continue 
    """

    async def get(
        self,
        url: str,
        retry_strategy: RetryStrategy,
        params: list[tuple] = [],
        headers: dict | None = None,
        use_myclient: bool = False,
    ) -> ResponseHander:
        # params.append(("version", self.version))  not necessary
        while self.isreloading:
            await asyncio.sleep(0.5)
        if use_myclient:
            client = self.myclient
        else:
            client = random.choice(self.client_pool)

        response = await self.retry_manager.execute_with_retry(
            lambda: client.get(url, headers=headers, params=params)
        )
        time.sleep(self.pause_time)
        if response.is_success:
            response_hander.set_response(response)
            if response_hander.check():
                break
            if isretry:
                self.logger.info("Auto retry failed.")
                response_hander.res_code = 1
                break
            else:
                isretry = True
                continue
            return response_hander
        else:
            if response.status_code == 401:
                self.logger.critical("Cookies Error, check and reset cookies.")
            elif response.status_code == 403:
                self.logger.warning("Access Forbidden")
            elif response.status_code == 404:
                self.logger.warning("Not Found or Hiden by User")
            elif response.status_code == 429:
                self.logger.warning(
                    "Too Many Reautes!\nThere may be a risk of being blocked, the program will\
                        be automatically stopped.\nSuggest reduce semaphore or add pause time."
                )
            else:
                self.logger.warning(f"Unhandled Status Code: {response.status_code}")
            raise RequestNotSuccess(response=response)


class RequestNotSuccess(Exception):
    def __init__(self, response: httpx.Response, *args: object) -> None:
        super().__init__(*args)
        self.response = response


class StopAll(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


"""
class FetchDataFailRetryStrategy(RetryStrategy):
    def __init__(self, max_retries: int = 0, priority: int = 1) -> None:
        super().__init__(max_retries, priority)

    def should_retry(self, attempt, exception) -> int:
        if isinstance(exception, RequestNotSuccess):
            if exception.response.status_code in [403, 404]:
                return -1
            elif exception.response.status_code in [401, 429]:
                raise StopAll()
        return 0

    def get_wait_time(self, attempt) -> int:
        return 0


class RequestErrorRetryStrategy(RetryStrategy):
    def __init__(self, max_retries: int = 3, priority: int = 10) -> None:
        super().__init__(max_retries, priority)
    
    def should_retry(self, attempt, exception):

        if isinstance(exception, httpx.RequestError):
            return attempt < self.max_retries
        return False

    def get_wait_time(self, attempt):
        return 2**attempt  # 指数退避


class ServerBusyRetryStrategy(RetryStrategy):
    def should_retry(self, attempt, exception):

        if isinstance(exception, HTTPError):
            status_code = exception.response.status_code
            if status_code in [500, 502, 503, 504]:
                return attempt < self.max_retries
        return False

    def get_wait_time(self, attempt):
        return 5 * (attempt + 1)


class TimeoutRetryStrategy(RetryStrategy):
    def should_retry(self, attempt, exception):

        if isinstance(exception, httpx.TimeoutException):
            return attempt < self.max_retries
        return False

    def get_wait_time(self, attempt):
        return 0
"""
