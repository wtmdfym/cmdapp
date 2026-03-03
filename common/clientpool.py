import httpx
import random
import time
from logging import Logger
from common import ConfigHander, ResponseHander, format_cookie


class ClientPool:
    """
    __headers: The headers when sending a HTTP request to pixiv
    version: Parameters in the Pixiv request link (usefulness unknown)
    cookies: The cookies when a request is sent to pixiv
    """

    __headers = {
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

        self.creat_my_client()
        self.creat_pool()

    @property
    def headers(self):
        return self.__headers

    def creat_my_client(self) -> None:
        self.logger.debug("Creat client------my account")
        cookies = self.config_hander.get_config("cookies")
        assert isinstance(cookies, dict)
        if self.test_client(cookies):
            self.myclient = httpx.AsyncClient(
                headers=self.__headers,
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
                headers=self.__headers,
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
            headers=self.__headers,
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

    async def get(
        self,
        url: str,
        response_hander: ResponseHander,
        params: list[tuple] = [],
        headers: dict | None = None,
        use_myclient: bool = False,
    ) -> ResponseHander:
        isretry: bool = False
        # params.append(("version", self.version))  not necessary
        while True:
            while self.isreloading:
                time.sleep(0.5)
            try:
                if isretry:
                    self.logger.info("Auto retry......")
                if use_myclient:
                    client = self.myclient
                else:
                    client = random.choice(self.client_pool)
                response = await client.get(url, headers=headers, params=params)
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
                elif response.status_code == 401:
                    self.logger.critical("Cookies Error, check and reset cookies.")
                    response_hander.res_code = 3
                    break
                elif response.status_code == 403:
                    self.logger.warning("Access Forbidden")
                    response_hander.res_code = 1
                    break
                elif response.status_code == 404:
                    self.logger.warning("Not Found or Hiden by User")
                    response_hander.res_code = 1
                    break
                elif response.status_code == 429:
                    self.logger.warning("Too Many Reauest, auto pause one minute")
                    time.sleep(60)
                    if isretry:
                        self.logger.warning(
                            "Auto retry failed.\nThere may be a risk of being blocked, the program will\
                             be automatically stopped.\nSuggest reduce semaphore or add pause time."
                        )
                        response_hander.res_code = 3
                        break
                    else:
                        isretry = True
                        continue
                else:
                    self.logger.warning(f"Unknown Error: {response.status_code}")
                    response_hander.res_code = 2
                    break
            except httpx.ConnectError:
                if isretry:
                    self.logger.info("Auto retry failed.")
                    response_hander.res_code = 3
                    break
                else:
                    self.logger.warning("Proxy Error, auto pause 5s, check your proxy!")
                    time.sleep(5)
                    self.reload_pool()
                    isretry = True
                    continue
            except httpx.ConnectTimeout:
                if isretry:
                    self.logger.info("Auto retry failed.")
                    response_hander.res_code = 1
                    break
                else:
                    self.logger.warning(
                        "ConnectTimeout, auto pause 5s, check network connection!"
                    )
                    time.sleep(5)
                    isretry = True
                    continue
            except httpx.HTTPError as exc:
                self.logger.error("Request failed.")
                self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
                self.reload_pool()
                if isretry:
                    self.logger.info("Auto retry failed.")
                    response_hander.res_code = 2
                    break
                else:
                    isretry = True
                    continue
            except Exception as exc:
                self.logger.error(f"Request failed---Unkown Error:\n{exc}")
                response_hander.res_code = 3
                break
            finally:
                time.sleep(self.pause_time)
        return response_hander


'''
    async def stream_download(
        self,
        event: asyncio.Event,
        request_info: tuple[str, str, dict[str, str]],
        path: str,
        isretry: bool = False,
    ) -> tuple[int, int | None]:
        """
        流式接收数据并写入文件
        return:
            int:
                0:success
                1:fail and skip
                2:fail and retry
                3:fail and record
                4:stop all requests
        """
        work_id, url, headers = request_info
        try:
            if not event.is_set():
                return (0, None)
            client = random.choice(self.client_pool)
            # client = httpx.AsyncClient()
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code == 403:
                    self.logger.warning("无访问权限------ID:%s" % work_id)
                    return (1, None)
                elif response.status_code == 404:
                    self.logger.warning("作品不存在------ID:%s" % work_id)
                    return (1, None)
                elif response.status_code == 429:
                    self.logger.warning("请求次数过多,自动暂停一分钟")
                    time.sleep(60)
                    if isretry:
                        self.logger.warning(
                            "Auto retry failed.,可能有封号风险,自动停止程序"
                        )
                        return (4, None)
                    else:
                        return (2, None)
                elif response.is_success:
                    with open(path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=1024):
                            if not event.is_set():
                                f.close()
                                os.remove(path)
                                return (0, None)
                            f.write(chunk)
                            f.flush()
                    # 检查图片是否完整
                    iscomplete = check_image(path)
                    if iscomplete:
                        return (0, None)
                    else:
                        os.remove(path)
                        return (1, None)
                else:
                    self.logger.warning(
                        "下载失败!---响应状态码:%d" % response.status_code
                    )
                    return (3, response.status_code)
        except httpx.ConnectError:
            if isretry:
                self.logger.info("Auto retry failed.")
                return (4, None)
            else:
                self.logger.warning("代理配置可能错误!  检查你的代理!")
                return (2, None)
        except httpx.ConnectTimeout:
            self.logger.warning("连接超时!  请检查你的网络!")
            if isretry:
                self.logger.info("Auto retry failed.")
                return (1, None)
            else:
                return (2, None)
        except httpx.HTTPError as exc:
            self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
            self.logger.error("获取作品信息失败\nID:%s" % work_id)
            return (3, None)
        except httpx._exceptions as exc:
            self.logger.debug(exc)
            self.logger.error("获取作品信息失败\nID:%s" % work_id)
            return (3, None)

    async def get_download(
        self,
        event: asyncio.Event,
        request_info: tuple[str, str, dict[str, str]],
        path: str,
        isimage: bool = True,
        isretry: bool = False,
    ) -> tuple[int, None]:
        """
        接收数据并写入文件
        return:
            int:
                0:success
                1:fail and skip
                2:fail and retry
                3:fail and record
                4:stop all requests
        """
        work_id, url, headers = request_info
        try:
            if not event.is_set():
                return (0, None)
            client = random.choice(self.client_pool)
            # client = httpx.AsyncClient()
            response = await client.get(url, headers=headers)
            if response.status_code == 403:
                self.logger.warning("无访问权限------ID:%s" % work_id)
                return (1, None)
            elif response.status_code == 404:
                self.logger.warning("作品不存在------ID:%s" % work_id)
                return (1, None)
            elif response.status_code == 429:
                self.logger.warning("请求次数过多,自动暂停一分钟")
                time.sleep(60)
                if isretry:
                    self.logger.warning(
                        "Auto retry failed.,可能有封号风险,自动停止程序"
                    )
                    return (4, None)
                else:
                    return (2, None)
            elif response.is_success:
                with open(path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024):
                        if not event.is_set():
                            f.close()
                            os.remove(path)
                            return (0, None)
                        f.write(chunk)
                        f.flush()
                # 检查图片是否完整
                if isimage:
                    iscomplete = check_image(path)
                    if iscomplete:
                        return (0, None)
                    else:
                        self.logger.warning("图片下载失败")
                        os.remove(path)
                        return (1, None)
                else:
                    return (0, None)
            else:
                self.logger.warning("下载失败!---响应状态码:%d" % response.status_code)
                return (3, response.status_code)
        except httpx.ConnectError:
            if isretry:
                self.logger.info("Auto retry failed.")
                return (4, None)
            else:
                self.logger.warning("代理配置可能错误!  检查你的代理!")
                return (2, None)
        except httpx.ConnectTimeout:
            self.logger.warning("连接超时!  请检查你的网络!")
            if isretry:
                self.logger.info("Auto retry failed.")
                return (1, None)
            else:
                return (2, None)
        except httpx.HTTPError as exc:
            self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
            self.logger.error("获取作品信息失败\nID:%s" % work_id)
            return (3, None)
        except httpx._exceptions as exc:
            self.logger.debug(exc)
            self.logger.error("获取作品信息失败\nID:%s" % work_id)
            return (3, None)
'''
