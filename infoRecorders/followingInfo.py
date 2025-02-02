import asyncio
import httpx
from mongoDB_hander import MongoDBHander


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

    __version = "54b602d334dbd7fa098ee5301611eda1776f6f39"
    __event = asyncio.Event()
    headers = {
        "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
        (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188",
        "referer": "https://www.pixiv.net/",
    }

    def __init__(
        self,
        client,
        mongoDb_hander: MongoDBHander,
        logger,
        semaphore: asyncio.Semaphore,
    ):
        self.client = client
        self.mongoDb_hander = mongoDb_hander
        self.logger = logger
        self.semaphore = semaphore
        self.__event.set()
        self.logger.info("实例化following recorder完成!")

    async def following_recorder(self, following_infos) -> int:
        if not self.__event.is_set():
            return 0
        self.logger.info("开始更新数据库......")
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
            earlier = await self.mongoDb_hander.find_one(
                key="userId", value=userId, collection="followings"
            )
            userName = following.get("userName")
            userComment = following.get("userComment")
            profileImageUrl = following.get("profileImageUrl")
            if earlier:
                self.logger.debug(
                    "Have been recorded:%s" % ({"userId": userId, "userName": userName})
                )
                earlier_userName = earlier.get("userName")
                earlier_userComment = earlier.get("userComment")
                earlier_profileImageUrl = earlier.get("profileImageUrl")
                if earlier_userName != userName:
                    self.logger.debug(
                        "Updating:%s to %s" % (earlier_userName, userName)
                    )
                    await self.mongoDb_hander.rename_user_collection(
                        earlier_userName, userName
                    )
                    # make sure update is successful
                    result = await self.mongoDb_hander.set_one(
                        key="userId",
                        value=userId,
                        setter={"userName": userName},
                        collection="followings",
                    )
                    if result:
                        self.logger.debug("Update Success")
                    else:
                        raise Exception("update failed")
                if earlier_userComment != userComment:
                    self.logger.debug("Updating userComment......")
                    result = await self.mongoDb_hander.set_one(
                        key="userId",
                        value=userId,
                        setter={"userComment": userComment},
                        collection="followings",
                    )
                    # make sure update is successful
                    if result:
                        self.logger.debug("Update Success")
                    else:
                        raise Exception("Update Failed")
                if earlier_profileImageUrl != profileImageUrl:
                    self.logger.debug("Updating profileImageUrl......")
                    result = await self.mongoDb_hander.set_one(
                        key="userId",
                        value=userId,
                        setter={"profileImageUrl": profileImageUrl},
                        collection="followings",
                    )
                    # make sure update is successful
                    if result:
                        self.logger.debug("Update Success")
                    else:
                        raise Exception("Update Failed")
            else:
                self.logger.debug(
                    "recording:{}".format({"userId": userId, "userName": userName})
                )
                result = await self.mongoDb_hander.insert_one(
                    {
                        "userId": userId,
                        "userName": userName,
                        "userComment": userComment,
                        "profileImageUrl": profileImageUrl,
                    },
                    collection="followings",
                )
                # make sure update is successful
                if result:
                    self.logger.debug("Insert Success")
                else:
                    raise Exception("Insert Failed")
        # 检查是否有已取消关注的作者
        earliers = self.mongoDb_hander.find_exist("userId", collection="followings")
        # count = 0
        # info_count = followings_collection.count_documents(
        #     {"userId": {"$exists": "true"}}
        # )
        async for earlier in earliers:
            userId = earlier.get("userId")
            userName = earlier.get("userName")
            not_following_now = earlier.get("not_following_now")
            if userId in userId_list:
                if not_following_now:
                    await self.mongoDb_hander.unset_one(
                        key="userId",
                        value=userId,
                        unset="not_following_now",
                        collection="followings",
                    )
                    print("已重新关注:%s" % {"userId": userId, "userName": userName})
            else:
                if not not_following_now:
                    await self.mongoDb_hander.set_one(
                        key="userId",
                        value=userId,
                        setter={"not_following_now": True},
                        collection="followings",
                    )
                print("已取消关注:%s" % {"userId": userId, "userName": userName})
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
                {"referer": "https://www.pixiv.net/users/83945559/following?p=1"}
            )
            try:
                response = await self.client.get(
                    url,
                    headers=self.headers,
                )
                if response.status_code == 401:
                    self.logger.warning("Cookies错误")
                followings_json = response.json()
                if followings_json.get("error"):
                    self.logger.error(
                        "请检查你的cookie是否正确\ninformation:%s" % (followings_json)
                    )
                    return
                    # raise Exception('请检查你的cookie是否正确',response)
                if not self.__event.is_set():
                    return
                body = followings_json.get("body")
                following = body.get("following")
                following_infos = await self.__get_followings(following)
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
        bookmark_url = "https://www.pixiv.net/ajax/user/83945559/illusts/bookmarks?tag=&offset={offset}&limit=48&rest=hide&lang=zh"
        bookmarked_works = []
        async with self.semaphore:
            while True:
                try:
                    response = await self.client.get(bookmark_url.format(offset=offset))
                    if response.status_code == 401:
                        self.logger.warning("Cookies错误")
                    bookmarked_json = response.json()
                    if bookmarked_json.get("error"):
                        self.logger.error(
                            "请检查你的cookie是否正确\ninformation:%s"
                            % (bookmarked_json)
                        )
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
                body = bookmarked_json.get("body")
                works = body.get("works")
                for work in works:
                    bookmarked_works.append(work.get("id"))
                if len(works) < 48:
                    break
                else:
                    offset += 48
        # print(bookmarked_works)
        # print(len(bookmarked_works))

    async def __get_followings(self, following: int):
        following_url = "https://www.pixiv.net/ajax/user/83945559/following?offset={offset}\
            &limit=24&rest=show&tag=&acceptingRequests=0&lang=zh&version={version}"
        userinfos = []
        all_page = following // 24 + 1
        for page in range(all_page):
            self.logger.info("获取作者列表......")
            if not self.__event.is_set():
                return
            # sys.stdout.write("\r获取关注作者页%d/%d" % (page + 1, all_page))
            # sys.stdout.flush()
            # self.headers.update(
            #     {"referer": "https://www.pixiv.net/users/83945559/following?p=%d" % page})
            following_url1 = following_url.format(
                offset=page * 24, version=self.__version
            )
            try:
                response = await self.client.get(
                    url=following_url1,
                    headers=self.headers,
                )
                response = response.json()
                body = response.get("body")
                users = body.get("users")
                for user in users:
                    userinfos.append(
                        {
                            "userId": user.get("userId"),
                            "userName": user.get("userName"),
                            "userComment": user.get("userComment"),
                            "profileImageUrl": user.get("profileImageUrl"),
                        }
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
        return userinfos

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
