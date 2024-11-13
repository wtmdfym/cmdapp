# -*-coding:utf-8-*-
from parsel import Selector
import asyncio
import httpx
import re
import json
import http.cookies
http.cookies._is_legal_key = lambda _: True
import time

from Tool import ClientPool


'''import motor.motor_asyncio
a = motor.motor_asyncio.AsyncIOMotorClient()
b = a[""]
c = b [""]
c.find()
c.count_documents({"userId": {"$exists": "true"}})'''


class FollowingsRecorder:
    """Get information about users you've followed


    Attributes:
        __version: Parameters in the Pixiv request link (usefulness unknown)
        __event: The stop event
        cookies: The cookies when a request is sent to pixiv
        db: Database of MongoDB
        logger: The instantiated object of logging.Logger
        progress_signal: The pyqtSignal of QProgressBar
        headers: The headers when sending a HTTP request to pixiv
    """
    __version = '54b602d334dbd7fa098ee5301611eda1776f6f39'
    __event = asyncio.Event()
    headers = {
    "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
    "referer": "https://www.pixiv.net/"}

    def __init__(self, client, asyncdb, logger, semaphore: asyncio.Semaphore, progress_signal=None):
        """Initialize followingrecoder class

        Initialize class variables and stop event

        Args:
            cookies(dict):The cookies of pixiv
            asyncdb(AsyncIOMotorDatabase):AsyncIOMotorDatabase of MongoDB
            logger(:class:`logging.Logger`):The instantiated object of logging.Logger
            progress_singal(:class:`PyQt6.QtCore.pyqtSignal`):The pyqtSignal of QProgressBar
        """
        '''
        self.cookies = config_dict.get('cookies')
        self.headers = {
            "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
            "referer": "https://www.pixiv.net/"}
        limits = httpx.Limits(
            max_keepalive_connections=config_dict.get("semaphore"), max_connections=config_dict.get("semaphore"))
        # 获取代理
        self.mounts = {
            "http://": httpx.AsyncHTTPTransport(proxy=config_dict.get("http_proxies"),
                                                limits=limits, retries=3),
            "https://": httpx.AsyncHTTPTransport(proxy=config_dict.get("https_proxies"),
                                                 limits=limits, retries=3),
        }
        self.client = httpx.AsyncClient(headers=self.headers, cookies=self.cookies, mounts=self.mounts)
        '''
        self.client = client
        self.asyncdb = asyncdb
        self.logger = logger
        self.progress_signal = progress_signal
        self.semaphore = semaphore
        self.__event.set()
        self.logger.info("实例化following recorder完成!")

    async def following_recorder(self, following_infos) -> int:
        if not self.__event.is_set():
            return 0
        self.logger.info("开始更新数据库......")
        followings_collection = self.asyncdb["All Followings"]
        # 记录当前关注的作者信息
        userId_list = []
        info_count = len(following_infos)
        for count in range(info_count):
            following = following_infos[count]
            userId = following.get("userId")
            userId_list.append(userId)
            # 跳过Pixiv官方的账户
            if userId == "11":
                continue
            earlier = await followings_collection.find_one({"userId": userId})
            userName = following.get("userName")
            userComment = following.get("userComment")
            if earlier:
                self.logger.debug(
                    "Have been recorded:%s" % (
                        {"userId": userId, "userName": userName})
                )
                earlier_userName = earlier.get("userName")
                earlier_userComment = earlier.get("userComment")
                if earlier_userName != userName:
                    self.logger.debug(
                        "Updating:%s to %s" % (earlier_userName, userName)
                    )
                    await self.__async_rename_collection(earlier_userName, userName)
                    # make sure update is successful
                    result = await followings_collection.update_one(
                        {"userId": userId}, {"$set": {"userName": userName}}
                    )
                    if result:
                        self.logger.debug("Update Success")
                    else:
                        raise Exception("update failed")
                if earlier_userComment != userComment:
                    self.logger.debug("Updating userComment......")
                    result = await followings_collection.update_one(
                        {"userId": userId}, {"$set": {"userComment": userComment}}
                    )
                    # make sure update is successful
                    if result:
                        self.logger.debug("Update Success")
                    else:
                        raise Exception("Update Failed")
            else:
                self.logger.debug(
                    "recording:{}".format(
                        {"userId": userId, "userName": userName})
                )
                result = await followings_collection.insert_one(
                    {"userId": userId, "userName": userName,
                        "userComment": userComment}
                )
                # make sure update is successful
                if result:
                    self.logger.debug("Insert Success")
                else:
                    raise Exception("Insert Failed")
            # self.progress_signal.emit(
            #     [("更新数据库......", int(100 * count / info_count))])
        # 检查是否有已取消关注的作者
        # {"userId": {"$exists": "true"}}
        earliers = followings_collection.find({"userId": {"$exists": "true"}})
        count = 0
        info_count = followings_collection.count_documents({"userId": {"$exists": "true"}})
        async for earlier in earliers:
            userId = earlier.get("userId")
            userName = earlier.get("userName")
            if userId in userId_list:
                pass
            else:
                await followings_collection.find_one_and_update(
                    {"userId": userId}, {'$set': {'not_following_now': True}})
                print("已取消关注:%s" % {"userId": userId, "userName": userName})
            # self.progress_signal.emit(
            #     [("检查数据库......", int(100 * count / info_count))])
        # self.progress_signal.emit([("更新数据库完成", 100)])
        self.logger.info("更新数据库完成")
        return 1

    async def following_work_fetcher(self) -> int:
        success = 0
        async with self.semaphore:
            self.logger.info("获取已关注的用户的信息......")
            url = "https://www.pixiv.net/ajax/user/extra?lang=zh&version={version}".format(
                version=self.__version
            )
            self.headers.update(
                {"referer": "https://www.pixiv.net/users/83945559/following?p=1"})
            try:
                response = await self.client.get(
                    url,
                    headers=self.headers,
                )
                if response.status_code == 401:
                    self.logger.warning("Cookies错误")
                followings_json = response.json()
                if followings_json.get("error"):
                    self.logger.error("请检查你的cookie是否正确\ninformation:%s" % (followings_json))
                    return
                    # raise Exception('请检查你的cookie是否正确',response)
                if not self.__event.is_set():
                    return
                body = followings_json.get("body")
                following = body.get("following")
                following_infos = await self.__async_get_my_followings(following)
                success = await self.following_recorder(following_infos)
            except asyncio.exceptions.TimeoutError:
                self.logger.warning("连接超时!  请检查你的网络!")
            except httpx.HTTPError as exc:
                self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
            except Exception as exc:
                self.logger.error(f"Unkonwn Exception - {exc}")
            finally:
                return success

    async def bookmarked_work_fetcher(self) -> int:
        success = 0
        self.logger.info("获取收藏的作品信息......")
        offset = 0
        bookmark_url = 'https://www.pixiv.net/ajax/user/83945559/illusts/bookmarks?tag=&offset={offset}&limit=48&rest=hide&lang=zh'
        bookmarked_works = []
        async with self.semaphore:
            while True:
                try:
                    response = await self.client.get(bookmark_url.format(offset=offset))
                    if response.status_code == 401:
                        self.logger.warning("Cookies错误")
                    bookmarked_json = response.json()
                    if bookmarked_json.get("error"):
                        self.logger.error("请检查你的cookie是否正确\ninformation:%s" % (bookmarked_json))
                        return
                        # raise Exception('请检查你的cookie是否正确',response)
                    if not self.__event.is_set():
                        return
                except asyncio.exceptions.TimeoutError:
                    self.logger.warning("连接超时!  请检查你的网络!")
                except httpx.HTTPError as exc:
                    self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
                except Exception as exc:
                    self.logger.error(f"Unkonwn Exception - {exc}")
                body = bookmarked_json.get('body')
                works = body.get("works")
                for work in works:
                    bookmarked_works.append(work.get('id'))
                if len(works) < 48:
                    break
                else:
                    offset += 48
        # print(bookmarked_works)
        # print(len(bookmarked_works))

    async def __async_get_my_followings(self, following: int):
        following_url = "https://www.pixiv.net/ajax/user/83945559/following?offset={offset}\
            &limit=24&rest=show&tag=&acceptingRequests=0&lang=zh&version={version}"
        userinfos = []
        all_page = following // 24 + 1
        for page in range(all_page):
            self.logger.info("获取作者列表......")
            if not self.__event.is_set():
                # self.progress_signal.emit([("No Process", 100)])
                return
            # self.progress_signal.emit(
            #     [("获取关注作者页......", int(100 * (page + 1)/all_page))])
            # sys.stdout.write("\r获取关注作者页%d/%d" % (page + 1, all_page))
            # sys.stdout.flush()
            # self.headers.update(
            #     {"referer": "https://www.pixiv.net/users/83945559/following?p=%d" % page})
            following_url1 = following_url.format(
                offset=page * 24, version=self.__version)
            try:
                response = await self.client.get(
                    url=following_url1,
                    headers=self.headers,
                )
                response = response.json()
                body = response.get("body")
                users = body.get("users")
                for user in users:
                    userId = user.get("userId")
                    userName = user.get("userName")
                    userComment = user.get("userComment")
                    userinfos.append(
                        {"userId": userId, "userName": userName,
                            "userComment": userComment}
                    )
            except asyncio.exceptions.TimeoutError:
                self.logger.warning("连接超时!  请检查你的网络!")
            except httpx.HTTPError as exc:
                self.logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
            except Exception as exc:
                self.logger.error(f"Unkonwn Exception - {exc}")
            finally:
                continue
            
        self.logger.info("获取关注作者完成")
        # self.progress_signal.emit([("No Process", 100)])
        return userinfos

    async def __async_rename_collection(self, name1: str, name2: str) -> None:
        """Rename the MongoDB collection

        Rename the collection when the author you follow changes the name

        Args:
            name1(str): The original name of a collection
            name2(str): The new name of a collection

        Returns:
            None
        """
        self.logger.debug("重命名数据库......")
        collection_1 = self.asyncdb[name1]
        collection_2 = self.asyncdb[name2]
        async for doc in collection_1.find({"id": {"$exists": True}}):
            # print(doc)
            doc.update({"username": name2})
            await collection_2.insert_one(doc)
        await collection_1.drop()

    def set_version(self, version: str) -> None:
        self.__version = version

    def stop_recording(self) -> None:
        """Stop the function from running

        Via :class:`threading.Event` to send a stop event

        Args:
            None

        Returns:
            None
        """
        self.__event.clear()
        self.logger.info("停止获取关注的作者信息")


class InfoFetcherHttpx:
    """
    Get information about works

    Use asyncio and httpx

    Attributes:
        __version: Parameters in the Pixiv request link (usefulness unknown)
        __proxies: Proxy to use aiohttp to send HTTP requests (optional)
        __event: The stop event
        db: The database connection of MongoDB(async)
        cookies:The cookies when a request is sent to pixiv
        download_type: The type of work to be downloaded
        backup_collection: A collection of backup of info(async)
        logger: The instantiated object of logging.Logger
        progress_signal: The pyqtSignal of QProgressBar
        headers: The headers when sending a HTTP request to pixiv
        timeout: The timeout period for aiohttp requests
        semaphore: The concurrent semaphore of asyncio
    """
    __version = '54b602d334dbd7fa098ee5301611eda1776f6f39'
    __event = asyncio.Event()
    headers = {
    "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
    "referer": "https://www.pixiv.net/"}

    def __init__(self, clientpool: ClientPool, download_type: dict, asyncdb, asyncbackupcollection, logger,
                 semaphore: asyncio.Semaphore, progress_signal=None) -> None:
        self.db = asyncdb
        self.download_type = download_type
        self.backup_collection = asyncbackupcollection
        self.logger = logger
        self.progress_signal = progress_signal
        self.clientpool = clientpool
        self.semaphore = semaphore
        self.__event.set()
        self.error_counter = 0
        self.logger.info("实例化work info fetcher完成!")

    async def start_get_info(self) -> bool | None:
        """
        Raises:
            Exception:
        """
        finish = await self.record_infos()
        if finish:
            success = await self.mongoDB_auto_backup()
            if success:
                return True
            else:
                return False
                # raise Exception("database backup error")

    async def record_infos(self) -> bool:
        self.followings_collection = self.db["All Followings"]
        _painters = self.followings_collection.find(
            {"userId": {"$exists": True}})
        painters = []
        async for painter in _painters:
            if painter.get('not_following_now'):
                continue
            else:
                painters.append(painter)
        for painter in painters:
            uid = painter.get("userId")
            name = painter.get("userName")
            name, ids = await self.get_id(user=(uid, name))
            collection = self.db[name]
            if ids:
                # 将图片详情信息保存在mongodb中
                async with self.semaphore:
                    exists = collection.find(
                        {"id": {"$exists": True}}, {"_id": 0, "id": 1})
                    exists_id = [id.get("id") async for id in exists]
                    # exists_id = [id.get("id") for id in exists]
                    for key in list(ids.keys()):
                        if not self.__event.is_set():
                            return
                        _ids = ids.get(key)
                        task_list = []
                        for _id in _ids:
                            if int(_id) in exists_id:
                                # res = await collection.find_one({'id': int(_id)})
                                # if res.get('type') == 'ugoira':
                                    # print(_id)
                                #     collection.find_one_and_delete({'id': int(_id)})
                                # print(find)
                                # print('已存在,跳过')
                                continue
                            _info = self.get_info(work_id=_id, collection=collection)
                            task = asyncio.create_task(_info)
                            task_list.append(task)
                        futurelist = await asyncio.gather(*task_list)              
                        for res in futurelist:
                            if not self.__event.is_set():
                                return
            else:
                print(6)
        # await self.client.aclose()
        if not self.__event.is_set():
            return False
        else:
            self.logger.info("获取所有作者的作品信息完成")
            return True

    async def get_id(self, tag=None, user: tuple[str, str]=None) -> dict:
        async with self.semaphore:
            """获取作者所有作品的id"""
            if not self.__event.is_set():
                return
            Ids = {}
            if tag is not None:
                pass

                # All_Ids['tag'] = Ids
                # 等待，防止封IP

            elif user is not None:
                uid, name = user
                self.logger.info("获取%s(uid:%s)的作品信息......" % (name, uid))
                self.headers.update(
                    {"referer": "https://www.pixiv.net/users/{}".format(uid)})
                xhr_url = (
                    "https://www.pixiv.net/ajax/user/{}/profile/all?lang=zh&version={}".format(
                        uid, self.__version)
                )
                _retry = False
                while True:
                    returncode, ids_json = await self.clientpool.send_get_request(xhr_url, uid, isretry=_retry)
                    if returncode == 1:
                        # 防封号
                        time.sleep(0.6)
                        return None
                    elif returncode == 2:
                        _retry = True
                        self.logger.info("自动重试......")
                        time.sleep(2)
                        continue
                    elif returncode == 3:
                        # TODO
                        pass
                    elif returncode == 4:
                        self.logger.warning("正在自动终止程序......")
                        # TODO
                        exit(0)
                    else:
                        break
                # print(ids_json)
                body = ids_json.get("body")
                # print(body)
                if isinstance(body, dict) is not True:
                    # raise Exception('[ERROR]获取ID失败!',body)
                    # print("[ERROR]获取ID失败!")
                    # print(ids_json)
                    self.logger.error("获取ID失败!\nIds:%s" % str(ids_json))
                    return None
                # 插图
                illusts = []
                _illusts = body.get("illusts")
                # print(_illusts)
                if isinstance(_illusts, dict) and _illusts is not None:
                    for illust in _illusts.keys():
                        illusts.append(illust)
                elif isinstance(_illusts, list) and (len(_illusts) == 0):
                    pass
                else:
                    raise Exception("[ERROR]获取插画失败!")
                # 漫画
                manga = []
                _mangas = body.get("manga")
                if isinstance(_mangas, dict) and _mangas is not None:
                    for _manga in _mangas.keys():
                        manga.append(_manga)
                elif isinstance(_mangas, list) and (len(_mangas) == 0):
                    pass
                else:
                    raise Exception("[ERROR]获取漫画失败!")
                # 漫画系列
                mangaSeries = str(re.findall(
                    "'mangaSeries'.*?}]", str(ids_json), re.S))
                # 小说系列
                novelSeries = str(re.findall(
                    "'novelSeries'.*?}]", str(ids_json), re.S))
                # 小说
                novels = str(re.findall("'novels'.*?}]", str(ids_json), re.S))

                # return ids
                if len(illusts) != 0 and self.download_type.get("illust"):
                    Ids["illusts"] = illusts
                if len(manga) != 0 and self.download_type.get("manga"):
                    Ids["manga"] = manga
                if len(mangaSeries) != 0 and self.download_type.get("mangaSeries"):
                    mangaSeries_1 = str(re.findall(
                        "'id':.*?,", mangaSeries, re.S))
                    mangaSeries_ids = re.findall("[0-9]+", mangaSeries_1, re.S)
                    Ids["mangaSeries"] = mangaSeries_ids
                if len(novelSeries) != 0 and self.download_type.get("novelSeries"):
                    novelSeries_1 = str(re.findall(
                        "'id':.*?,", novelSeries, re.S))
                    novelSeries_ids = re.findall("[0-9]+", novelSeries_1, re.S)
                    Ids["novelSeries"] = novelSeries_ids
                if len(novels) != 0 and self.download_type.get("novel"):
                    novels_1 = str(re.findall("'id':.*?,", novels, re.S))
                    novels_ids = re.findall("[0-9]+", novels_1, re.S)
                    Ids["novels"] = novels_ids
            # await asyncio.sleep(0.5)
            return (name, Ids)

    async def get_info(self, work_id: str, collection) -> dict:
        """
        Get detailed information about a work
        TODO illust_info:It's not the same if you want to climb other types of works!

        Args:
            url(str): Request link
            id(str): The ID of the work
            session(aiohttp.ClientSession): Connection session with pixiv

        Returns:

            A dictionary of work information. Include the ID, title, description,
            tags, download link of the original image (if it is an image), author ID,
            author's name, and relative storage path. For example:

            {"id": 100774433,
                "title": "夏生まれ",
                "description": "らむねちゃん応援してます(๑╹ᆺ╹)",
                "tags": {
                    "バーチャルYouTuber": "虚拟主播",
                    "ぶいすぽっ!": "Virtual eSports Project",
                    "白波らむね": "Shiranami Ramune",
                    "可愛い": "可爱",
                    "夏": "夏天",
                    "海": "sea",
                    "女の子": "女孩子",
                    "青髪": None
                },
                "original_url": [
                    "https://i.pximg.net/img-original/img/2022/08/26/19/00/13/100774433_p0.png"
                ],
                "userId": "9155411",
                "username": "rucaco/るかこ",
                "relative_path": [
                    "picture/9155411/100774433_p0.png"
                ]
            }

        Raises:
            Exception: The parsing method is incorrect
        """
        async with self.semaphore:
            if not self.__event.is_set():
                return
            self.logger.info("获取作品信息......ID:%s" % work_id)
            artworksurl = 'https://www.pixiv.net/artworks/' + work_id
            # novelurl
            # seriesurl
            _retry = False
            while True:
                url = artworksurl #+ work_id
                returncode, work_html = await self.clientpool.send_get_request(url, work_id, isjson=False, isretry=_retry)
                if returncode == 1:
                    # 防封号
                    time.sleep(0.6)
                    return None
                elif returncode == 2:
                    _retry = True
                    self.logger.info("自动重试......")
                    time.sleep(2)
                    continue
                elif returncode == 3:
                    # TODO
                    return None
                elif returncode == 4:
                    self.logger.warning("正在自动终止程序......")
                    # TODO
                    exit(0)
                else:
                    # print(returncode)
                    # print(work_html)
                    infoparsel = InfoParsel(work_html, self.clientpool, self.logger)
                    info = await infoparsel.get_result()
                    if info:
                        break
                    else:
                        # self.logger.warning("获取的html异常!")
                        # self.logger.debug(work_html)
                        if _retry:
                            time.sleep(2)
                            return None
                        else:
                            _retry = True
                            self.logger.info("自动重试......")
                            time.sleep(2)
                            continue
            res = await collection.insert_one(info)
            assert res, "记录info失败------%s" % info
            await self.record_in_tags(info.get("id"), info.get("tags"))
            # 防封号
            time.sleep(0.6)
            return None

    async def record_in_tags(self, id: int, tags) -> None:
        self.tags_collection = self.db["All Tags"]
        for name, translate in tags.items():
            earlier = await self.tags_collection.find_one({'name': name})
            if earlier:
                workids = earlier.get("workids")
                if workids:
                    workids.append(id)
                else:
                    workids = [id]
                works_count = earlier.get('works_count')+1
                earlier_translate = earlier.get('translate')
                if earlier_translate is None and translate:
                    await self.tags_collection.update_one(
                        {"name": name}, {"$set": {"translate": translate, 'works_count': works_count, "workids": workids}})
                elif earlier_translate and translate:
                    if translate in earlier_translate.split('||'):
                        await self.tags_collection.update_one(
                            {"name": name}, {"$set": {'works_count': works_count, "workids": workids}})
                    else:
                        await self.tags_collection.update_one({"name": name},
                                                              {"$set": {"translate": earlier_translate+'||'+translate,
                                                                        'works_count': works_count, "workids": workids}})
                elif (earlier_translate and translate) is None:
                    await self.tags_collection.update_one(
                        {"name": name}, {"$set": {'works_count': works_count, "workids": workids}})
                else:
                    print(id)
                    return
            else:
                res = await self.tags_collection.insert_one(
                    {'name': name, 'translate': translate, 'works_count': 1, "workids": [id]})
                assert res, "记录tag失败------%s" % id

    async def mongoDB_auto_backup(self) -> bool:
        self.logger.info("开始自动备份,请勿关闭程序!!!")
        names = await self.db.list_collection_names()
        for name in names:
            collection = self.db[name]
            # 可不用
            async with self.semaphore:
                async for docs in collection.find({"id": {"$exists": True}}, {"_id": 0}):
                    if not self.__event.is_set():
                        self.logger.info("停止自动备份!")
                        return False
                    if len(docs) >= 9:
                        b = await self.backup_collection.find_one({"id": docs.get("id")})
                        if b:
                            continue
                        else:
                            await self.backup_collection.insert_one(docs)
                            # print(c)
        self.logger.info("自动备份完成!")
        return True

    def set_version(self, version: str):
        self.__version = version

    def stop_getting(self):
        self.__event.clear()
        self.logger.info("停止获取作者的作品信息......")


class InfoParsel:
    def __init__(self, work_html: str, clientpool: ClientPool, logger) -> None:
        self.clientpool = clientpool
        self.logger = logger
        selector = Selector(text=work_html)
        preload_datas = selector.xpath(
            '//meta[@id="meta-preload-data"]/@content').get()
        # or re.search("error-message", work_html, re.S)
        if not preload_datas:
            logger.warning('解析方式可能错误')
            return None
        info_json = json.loads(preload_datas, strict=False)
        # print(info_json)
        infos = info_json.items()
        assert len(infos) == 3, "解析方式错误------all"
        _infos = []
        for _info in infos:
            _infos.append(_info)
        self.infos = _infos[1]
        del _infos
        if self.infos[0] == "illust":
            illust_infos = self.infos[1].popitem()
            self.work_id, work_info = illust_infos
            work_type = work_info.get("illustType")
            if work_type == 0:
                self.work_type = "illust"
            elif work_type == 1:
                self.work_type = "manga"
            elif work_type == 2:
                self.work_type = "ugoira"
            # illust_info = info_json.get("illust").get(id)
            # print(illust_info)
            self.work_info = work_info
            # self.result = self.fetch_artworks_links()
        elif self.infos[0] == "novel":
            novel_infos = self.infos[1].popitem()
            self.work_id, work_info = novel_infos
            self.work_type = "novel"
            self.work_info = work_info
            # self.result = self.fetch_novel()
        # self.work_type =

    async def fetch_artworks_links(self) -> dict:
        self.logger.debug('解析作品信息......')
        # title1 = illust_info.get("illustTitle")
        title = self.work_info.get("title")
        description = self.work_info.get("description")
        tags = {}
        for text in self.work_info.get("tags").get("tags"):
            tag = text.get("tag")
            translation = text.get("translation")
            if translation:
                translation = translation.get("en")
            tags.update({tag: translation})
        # all_url = re.search('(?<=urls":{).*?(?=})',info_2,re.S).group()
        userId = self.work_info.get("userId")
        username = self.work_info.get("userName")
        # userAccount = illust_info.get("userAccount")
        uploadDate = self.work_info.get("uploadDate")
        likeData = self.work_info.get("likeData")
        likeCount = self.work_info.get("likeCount")
        bookmarkCount = self.work_info.get("bookmarkCount")
        viewCount = self.work_info.get("viewCount")
        isOriginal = self.work_info.get("isOriginal")
        info = {
            "type": self.work_type,
            "id": int(self.work_id),
            "title": title,
            "description": description,
            "tags": tags,
            "userId": userId,
            "username": username,
            "uploadDate": uploadDate,           # 上传日期
            "likeData": likeData,               # 我的点赞信息
            "likeCount": likeCount,             # 点赞数
            "bookmarkCount": bookmarkCount,     # 收藏数
            "viewCount": viewCount,             # 浏览数
            "isOriginal": isOriginal,           # 原创作品
        }
        # print(info)
        # ====================================
        #             获取原图链接
        # ====================================
        # 原图链接
        original_urls = []
        # 图片保存路径
        relative_path = []
        if (self.work_type == "illust") or (self.work_type == "manga"):
            xhr_url = "https://www.pixiv.net/ajax/illust/%s/pages?" % self.work_id
        elif self.work_type == "ugoira":
            xhr_url = "https://www.pixiv.net/ajax/illust/%s/ugoira_meta?" % self.work_id
        else:
            return None
        # headers = {
        #      'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) \
        #         AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
        #     "referer": "https://www.pixiv.net/artworks/%s" % self.work_id}
        # params = {"lang": "zh"}
        # "version": "54b602d334dbd7fa098ee5301611eda1776f6f39"}
        # headers.update(
        #     {"referer": "https://www.pixiv.net/artworks/%d" % work_id})
        # requests = client.build_request("GET", xhr_url, params=params, headers=headers)
        # print(str(requests.url))
        _retry = False
        while True:
            returncode, img_json = await self.clientpool.send_get_request(xhr_url, self.work_id, isretry=_retry)
            #print(returncode, img_json)
            if returncode == 1:
                # 防封号
                time.sleep(0.6)
                return None
            elif returncode == 2:
                _retry = True
                self.logger.info("自动重试......")
                time.sleep(2)
                continue
            elif returncode == 3:
                # TODO
                return None
            elif returncode == 4:
                self.logger.warning("正在自动终止程序......")
                # TODO
                exit(0)
            else:
                break
        body = img_json.get("body")
        if (self.work_type == "illust") or (self.work_type == "manga"):
            for one in body:
                urls = one.get("urls")
                original = urls.get("original")
                name = re.search(r"[0-9]+\_.*", original).group()
                relative_path.append(
                    "picture/" + userId + "/" + name)
                original_urls.append(original)
        elif self.work_type == "ugoira":
            # print(body)
            originalSrc = body.get("originalSrc")
            original_urls.append(originalSrc)
            name = re.search(r"[0-9]+\_ugoira", originalSrc).group()
            name = re.sub("_ugoira", ".gif", name)
            relative_path.append("picture/" + userId + "/" + name)
            frames = body.get("frames")
            info.update({'frames': frames})
        info.update({'original_url': original_urls,
                    'relative_path': relative_path})
        for key in info:
            if info.get(key) is None and key != "description":
                raise Exception("解析方式错误---%s" % info)
        # 防封号
        time.sleep(0.6)
        # print(info)
        return info

    def fetch_series(self):
        pass

    def fetch_novel(self):
        # title1 = illust_info.get("illustTitle")
        title = self.work_info.get("title")
        # if title != title1:
        #     raise Exception("解析方式错误---title")
        # description1 = illust_info.get("illustComment")
        description = self.work_info.get("description")
        # if description1 != description:
        #     raise Exception("解析方式错误---description")
        # tags1 = work_info.get("tags").get("tags")
        tags = {}
        for text in self.work_info.get("tags").get("tags"):
            tag = text.get("tag")
            translation = text.get("translation")
            if translation:
                translation = translation.get("en")
            tags.update({tag: translation})
        # del tags1, title1, description1
        # all_url = re.search('(?<=urls":{).*?(?=})',info_2,re.S).group()
        userId = self.work_info.get("userId")
        username = self.work_info.get("userName")
        # userAccount = illust_info.get("userAccount")
        uploadDate = self.work_info.get("uploadDate")
        likeData = self.work_info.get("likeData")
        likeCount = self.work_info.get("likeCount")
        bookmarkCount = self.work_info.get("bookmarkCount")
        viewCount = self.work_info.get("viewCount")
        isOriginal = self.work_info.get("isOriginal")
        text = self.work_info.get("content")
        coverUrl = self.work_info.get("coverUrl")
        info = {
            "type": self.work_type,
            "id": int(self.work_id),
            "title": title,
            "description": description,
            "tags": tags,
            "userId": userId,
            "username": username,
            "uploadDate": uploadDate,
            "likeData": likeData,
            "likeCount": likeCount,             # 赞
            "bookmarkCount": bookmarkCount,     # 收藏
            "viewCount": viewCount,
            "isOriginal": isOriginal,           # 原创作品
            "text": text,  # 小说文本
            "coverUrl": coverUrl}
        for key in info:
            if info.get(key) is None and key != "description":
                raise Exception("解析方式错误---%s" % info)
        return info

    async def get_result(self):
        result = None
        try:
            if (self.infos[0] == "illust") or (self.infos[0] == "manga") or (self.infos[0] == "ugoria"):
                result = await self.fetch_artworks_links()
            elif self.infos[0] == "novel":
                result = self.fetch_novel()
            else:
                print(6)
            return result
        except AttributeError:
            return result
