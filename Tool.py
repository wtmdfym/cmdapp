import httpx
import logging
import json
import os
import random
import re
import asyncio
import time
from PIL import Image


def format_cookie(oringal_cookies):
        cookies = {}
        for cookie in oringal_cookies.split(";"):
            key, value = cookie.split("=", 1)
            key = re.sub(' ', '', key)
            value = re.sub(' ', '', value)
            cookies[key] = value
        return cookies


def compare_datetime(lasttime: str, newtime: str) -> bool:
    time1 = [lasttime[0:4], lasttime[4:6], lasttime[6:8]]
    time2 = [newtime[0:4], newtime[4:6], newtime[6:8]]
    # print(time1,time2)
    if time2[0] > time1[0]:
        return True
    elif time2[0] == time1[0]:
        if time2[1] > time1[1]:
            return True
        elif time2[1] == time1[1]:
            return time2[2] > time1[2]
    return False

class MyLogging(logging.Logger):
    def __init__(self, name: str, level: int | str = 0) -> None:
        super().__init__(name, level)

    def init(self, usestream, infodisplayer=None) -> None:
        if usestream:
            self.usestream = True
        else:
            self.usestream = False
            self.infodisplayer = infodisplayer

    def debug(self,
              msg: object,
              *args: object,
              exc_info=None,
              stack_info: bool = False,
              stacklevel: int = 1,
              extra=None) -> None:
        if self.usestream:
            return super().debug(
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra)

    def info(
        self,
        msg: object,
        *args: object,
        exc_info=None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra=None,
    ) -> None:
        if self.usestream:
            return super().info(
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra,
            )
        else:
            self.infodisplayer.append("[INFO] - %s" % msg)

    def warning(
        self,
        msg: object,
        *args: object,
        exc_info=None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra=None,
    ) -> None:
        if self.usestream:
            return super().warning(
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra,
            )
        else:
            self.infodisplayer.append("[WARNING] - %s" % msg)

    def error(
        self,
        msg: object,
        *args: object,
        exc_info=None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra=None,
    ) -> None:
        if self.usestream:
            return super().error(
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra,
            )
        else:
            self.infodisplayer.append("[ERROR] - %s" % msg)

    def critical(
        self,
        msg: object,
        *args: object,
        exc_info=None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra=None,
    ) -> None:
        if self.usestream:
            return super().critical(
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra,
            )
        else:
            self.infodisplayer.append("[CRITICAL] - %s" % msg)


class ConfigSetter:
    def __init__(self) -> None:
        pass

    @classmethod
    def get_config(cls, config_file_path: str, default_config_save_path: str) -> dict:
        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
        else:
            with open(default_config_save_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
        return config_dict

    @classmethod
    def set_config(cls, config_file_path: str, config_dict: dict) -> None:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=4)


class ClientPool:
    def __init__(self, config_dict: dict, config_save_path, logger) -> None:
        logger.info("初始化连接池......")
        self.config_dict = config_dict
        self.config_save_path = config_save_path
        self.logger = logger
        # 获取连接池cookie
        self.client_pool_info = self.config_dict.get("client_pool")
        if self.client_pool_info is None:
            self.client_pool_info = []
        # 初始化连接池
        self.client_pool = []
        # 已添加的账号
        self.added_account = []
        # ============初始化httpx client============
        self.version = '54b602d334dbd7fa098ee5301611eda1776f6f39'
        self.headers = {
            "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
            "referer": "https://www.pixiv.net/"}
        self.timeout = httpx.Timeout(8.0, connect=10.0, read=25.0, pool=None)
        semaphore = self.config_dict.get("semaphore")
        limits = httpx.Limits(
            max_keepalive_connections=semaphore, max_connections=semaphore)
        # 配置代理
        self.mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=config_dict.get("http_proxies"),
                                                limits=limits, retries=3),
            "https://": httpx.AsyncHTTPTransport(proxy=config_dict.get("https_proxies"),
                                                 limits=limits, retries=3),
        }
        # 创建连接池
        self.creat_my_client()
        self.creat_pool()

    def creat_my_client(self) -> None:
        self.logger.debug("创建连接------my account")
        cookies = self.config_dict.get('cookies')
        # 检查Cookie是否正确/可用
        # if (20 <= len(cookies) <= 29) is not True:
        #     self.logger.warning("Cookies设置错误!------Account email: %s" % client_info.get("email"))
        if self.test_client(cookies):
            self.myclient = httpx.AsyncClient(headers=self.headers, cookies=cookies,
                                        timeout=self.timeout, mounts=self.mounts)
            self.logger.debug("成功")
        else:
            self.logger.warning("Cookies设置错误!------my account")

    def creat_pool(self) -> None:
        if self.client_pool_info is not None:
            for client_info in self.client_pool_info:
                self.added_account.append(client_info.get("email"))
                client = self.creat_client(client_info)
                if client is not None:
                    self.client_pool.append(client)
        else:
            self.logger.warning("未添加pixiv连接池账号, 将使用个人账号!")
            client = self.creat_client({"cookies": self.config_dict.get('cookies')})
            if client is not None:
                self.client_pool.append(client)
        if len(self.client_pool) == 0:
            self.logger.warning("无任何可用账号,连接池启动失败!")
            # self.logger.info("程序终止......")
            # exit(0)
        else:
            self.logger.info("连接池启动成功!")

    def add_client(self, email: str,passward: str ) -> bool:
        if email in self.added_account:
            update_cookie = input("Pixiv账号已记录,是否更新Cookies?(y/n)")
            if update_cookie == ('n' or 'N'):
                return
            else:
                for client_info in self.client_pool_info:
                    if client_info.get("email") == email:
                        self.client_pool_info.remove(client_info)
                self.logger.info("重载连接池......")
                self.client_pool.clear()
                self.creat_pool()
        # 自动获取新账号的cookie
        # TODO
        # 手动输入
        oringal_cookies = input("输入你Pixiv账号的Cookies:")
        cookies = format_cookie(oringal_cookies)
        # 检查Cookie是否正确
        assert (20 <= len(cookies) <= 29) , "Cookies错误!------Account email: %s\nCookies: %s" % (email, cookies)
        assert cookies.get('PHPSESSID') , "Cookies错误!------Account email: %s\nCookies: %s" % (email, cookies)
        # if (20 <= len(cookies) <= 29) is not True:
        #         self.logger.warning("Cookies设置错误!------Account email: %s" % client_info.get("email"))
        # 测试连接
        self.logger.info("正在测试连接......")
        if self.test_client(cookies):
            # 更新连接配置文件
            client_info = {"email": email, "passward": passward, "cookies": cookies}
            self.client_pool_info.append(client_info)
            self.config_dict.update({"client_pool": self.client_pool_info})
            ConfigSetter.set_config(self.config_save_path, self.config_dict)
            self.logger.info("账号添加成功!")
            # 创建新连接
            client = self.creat_client(client_info)
            self.client_pool.append(client)
            self.logger.info("连接添加成功!")
        else:
            self.logger.warning("连接添加失败------该账号无法访问pixiv个人主页!")

    def creat_client(self, client_info: dict) -> httpx.AsyncClient:
        self.logger.debug("创建连接------email:%s" % client_info.get("email"))
        cookies = client_info.get("cookies")
        # 检查Cookie是否正确/可用
        # if (20 <= len(cookies) <= 29) is not True:
        #     self.logger.warning("Cookies设置错误!------Account email: %s" % client_info.get("email"))
        if self.test_client(cookies):
            client = httpx.AsyncClient(headers=self.headers, cookies=cookies,
                                        timeout=self.timeout, mounts=self.mounts)
            self.logger.debug("成功")
            return client
        else:
            self.logger.warning("Cookies设置错误!------Account email: %s" % client_info.get("email"))

    def get_client(self) -> httpx.AsyncClient:
        return random.choice(self.client_pool)
    
    async def send_get_request(self, url: str, work_id: str, headers: dict=None, isjson: bool=True, isretry: bool=False) -> tuple[int, str|dict|None]:
        '''
        return:
            int:
                0:success
                1:fail and skip
                2:fail and retry
                3:fail and record
                4:stop all requests
            Response:
                str:html
                dict:json
        '''
        data = None
        try:
            client = random.choice(self.client_pool)
            # client = httpx.AsyncClient()
            if headers:
                response = await client.get(url, headers=headers)   # , params=params
            else:
                response = await client.get(url)
            if response.status_code == 403:
                self.logger.warning("无访问权限------ID:%s" % work_id)
                return (1, None)
            elif response.status_code == 404:
                self.logger.warning("作品可能不存在或账号已屏蔽作品------ID:%s" % work_id)
                return (1, None)
            elif response.status_code == 429:
                self.logger.warning("请求次数过多,自动暂停一分钟")
                time.sleep(60)
                if isretry:
                    self.logger.warning("自动重试失败,可能有封号风险,自动停止程序")
                    return (4, None)
                else:
                    return (2, None)
            elif response.is_success:
                if isjson:
                    data = response.json()
                    if isinstance(data, dict):
                        if data.get("error"):
                            self.logger.warning("访问错误------message:%s" % data.get("message"))
                            if isretry:
                                self.logger.info("自动重试失败")
                                return (1, None)
                            else:
                                return (2, None)
                        else:
                            return(0, data)
                    else:
                        self.logger.warning("解析JSON失败!")
                        if isretry:
                            self.logger.info("自动重试失败")
                            return (1, None)
                        return (2, None)
                else:
                    data = response.text
                    return (0, data)
            else:
                self.logger.warning("获取作品信息失败\nID:%s------%d" %
                                    (work_id, response.status_code))
                return None
        except httpx.ConnectError:
            if isretry:
                self.logger.info("自动重试失败")
                return (4, None)
            else:
                self.logger.warning("代理配置可能错误!  检查你的代理!")
                return (2, None)
        except httpx.ConnectTimeout:
            self.logger.warning("连接超时!  请检查你的网络!")
            if isretry:
                self.logger.info("自动重试失败")
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

    async def stream_download(self, event: asyncio.Event, request_info: tuple[str, str, dict[str, str]], path: str, isretry: bool=False) -> tuple[int, int|None]:
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
                        self.logger.warning("自动重试失败,可能有封号风险,自动停止程序")
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
                    self.logger.warning("下载失败!---响应状态码:%d" % response.status_code)
                    return (3, response.status_code)
        except httpx.ConnectError:
            if isretry:
                self.logger.info("自动重试失败")
                return (4, None)
            else:
                self.logger.warning("代理配置可能错误!  检查你的代理!")
                return (2, None)
        except httpx.ConnectTimeout:
            self.logger.warning("连接超时!  请检查你的网络!")
            if isretry:
                self.logger.info("自动重试失败")
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

    async def get_download(self, event: asyncio.Event, request_info: tuple[str, str, dict[str, str]], path: str, isimage: bool = True, isretry: bool=False) -> tuple[int, None]:
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
                    self.logger.warning("自动重试失败,可能有封号风险,自动停止程序")
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
                self.logger.info("自动重试失败")
                return (4, None)
            else:
                self.logger.warning("代理配置可能错误!  检查你的代理!")
                return (2, None)
        except httpx.ConnectTimeout:
            self.logger.warning("连接超时!  请检查你的网络!")
            if isretry:
                self.logger.info("自动重试失败")
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

    def test_client(self, cookies: dict) -> bool:
        self.logger.debug("测试连接......")
        # 获取代理
        mounts = {
            "http://": httpx.HTTPTransport(proxy=self.config_dict.get("http_proxies"), retries=3),
            "https://": httpx.HTTPTransport(proxy=self.config_dict.get("https_proxies"), retries=3),
        }
        client = httpx.Client(headers=self.headers, cookies=cookies,
                            timeout=self.timeout, mounts=mounts)
        res = client.get("https://www.pixiv.net/settings/account")
        # res = client.get("https://www.pixiv.net/ajax/user/25170019/profile/all?lang=zh&version=54b602d334dbd7fa098ee5301611eda1776f6f39")
        # print(res.json())
        # exit(0)
        if res.status_code == 200:
            return True
        # elif res.status_code == 302:
            # return False
        else:
            return False
            # raise ("Unkonwn status_code:%d" % res.status_code)


def check_image(path: str) -> bool:
    print("checking work:%s" % path)
    if os.path.exists(path):
        '''
        with open(image_path, 'rb') as f:
            buf = f.read()
            if buf[6:10] in (b'JFIF', b'Exif'):     # jpg图片
                if not buf.rstrip(b'\0\r\n').endswith(b'\xff\xd9'):
                    bValid = False
            else:
                try:
                    Image.open(f).verify()
                except Exception:
                    bValid = False
        '''
        with open(path, 'rb') as f:
            try:
                Image.open(f).verify()
                image = Image.open(f)
                # 若图片大部分为灰
                valid_1 = image.getpixel((image.width - 1, image.height - 1)) == (128, 128, 128)
                valid_2 = image.getpixel((int(image.width / 2), image.height - 1)) == (128, 128, 128)
                valid_3 = image.getpixel((0, image.height - 1)) == (128, 128, 128)
                if valid_1 and valid_2 and valid_3:
                    return False
                else:
                    return True
            except Exception:   # OSERRor
                return False
    else:
        return False

class ErrorHander(enumerate):
    def __init__(self) -> None:
        super().__init__()

# print(check_image('C:/Users/Administrator/Desktop/120205761_p0.jpg'))
# work_type = "manga"
# print((work_type == "illust") or (work_type == "manga"))