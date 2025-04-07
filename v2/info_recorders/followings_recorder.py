from asyncio import Event
from common import ClientPool, ResponseHander, MongoDBHander
from logging import Logger


class FollowingsRecorder:
    """Get information about users you've followed


    Attributes:
        __event: The stop event
        mongoDb_hander: Hander of MongoDB
        logger: The instantiated object of logging.Logger
    """

    __event = Event()

    def __init__(
        self,
        clientpool: ClientPool,
        mongoDb_hander: MongoDBHander,
        logger: Logger,
        myId: str,
    ):
        logger.info("Initialize following recorder......")
        self.clientpool = clientpool
        self.mongoDb_hander = mongoDb_hander
        self.logger = logger
        self.myId = myId
        self.__event.set()

    async def start(self) -> bool:
        self.logger.info("Fetching following usesrs info.....")
        url = "https://www.pixiv.net/ajax/user/extra?lang=zh"
        headers = self.clientpool.headers.update(
            {"referer": f"https://www.pixiv.net/users/{self.myId}/following?p=1"}
        )
        response_hander = ResponseHander(self.logger, True)
        response_hander.set_processor({"REQUIRE": "body.following"})
        response_hander = await self.clientpool.get(
            url,
            response_hander=response_hander,
            headers=headers,
            use_myclient=True,
        )
        if response_hander.res_code:
            self.logger.warning("Request failed.")
            if response_hander.res_code == 2:
                await self.mongoDb_hander.record_error()
            elif response_hander.res_code == 3:
                self.stop()
            return False
        following = response_hander.processed_response
        if not isinstance(following, int):
            return False
        return await self._followings_fetcher(following)

    async def _followings_fetcher(self, following: int) -> bool:
        self.logger.info("Fetching folowings list......")
        following_url = f"https://www.pixiv.net/ajax/user/{self.myId}/following"
        userId_list: list[int] = []
        all_page = following // 24 + 1
        for page in range(all_page):
            if not self.__event.is_set():
                return False
            # sys.stdout.write("\r获取关注作者页%d/%d" % (page + 1, all_page))
            # sys.stdout.flush()
            response_hander = ResponseHander(self.logger, True)
            response_hander.set_processor({"REQUIRE": "body.users"})
            response_hander = await self.clientpool.get(
                url=following_url,
                response_hander=response_hander,
                params=[
                    ("offset", page * 24),
                    ("limit", 24),
                    ("rest", "show"),
                    ("tag", None),
                    ("acceptingRequests", 0),
                    ("lang", "zh"),
                ],
                use_myclient=True,
            )
            if response_hander.res_code:
                self.logger.warning("Request failed.")
                if response_hander.res_code == 2:
                    await self.mongoDb_hander.record_error()
                elif response_hander.res_code == 3:
                    self.stop()
                return False
            users = response_hander.processed_response
            if not isinstance(users, list):
                return False
            for user in users:
                if not isinstance(user, dict):
                    return False
                userId = await self._following_info_updater(user)
                if userId is not None:
                    userId_list.append(userId)
        self.logger.info("Fetch complete.")

        self.logger.info("Checking not following users......")
        earliers = self.mongoDb_hander.find_exist("userId", collection="followings")
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
                    self.logger.info(
                        "Following again:%s" % {"userId": userId, "userName": userName}
                    )
            else:
                if not not_following_now:
                    await self.mongoDb_hander.set_one(
                        key="userId",
                        value=userId,
                        setter={"not_following_now": True},
                        collection="followings",
                    )
                self.logger.warning(
                    "Not following now:%s" % {"userId": userId, "userName": userName}
                )
        self.logger.info("Database update complete.")
        return True

    async def _following_info_updater(self, following_info: dict) -> None | int:
        """Record or update following info in mongoDB"""
        userId = following_info["userId"]
        # Skip Pixiv official account
        if userId == "11":
            return None
        userName = following_info["userName"]  # make sure it exist
        userComment = following_info.get("userComment")
        profileImageUrl = following_info.get("profileImageUrl")
        earlier = await self.mongoDb_hander.find_one(
            key="userId", value=userId, collection="followings"
        )

        if earlier:
            self.logger.debug(f"Have been recorded: UID: {userId}   Name: {userName}")
            earlier_userName = earlier.get("userName")
            earlier_userComment = earlier.get("userComment")
            earlier_profileImageUrl = earlier.get("profileImageUrl")
            setter = earlier
            if earlier_userName != userName:
                await self.mongoDb_hander.rename_user_collection(
                    earlier_userName, userName
                )
                setter["userName"] = userName
            if earlier_userComment != userComment:
                setter["userComment"] = userComment
            if earlier_profileImageUrl != profileImageUrl:
                setter["profileImageUrl"] = profileImageUrl
            if setter != earlier:
                self.logger.info(f"Updating user info from {earlier} to {setter}.")
                result = await self.mongoDb_hander.set_one(
                    key="userId",
                    value=userId,
                    setter=setter,
                    collection="followings",
                )
                # make sure update is successful
                if result:
                    self.logger.debug("Update Success")
                else:
                    raise Exception("Update Failed")
        else:
            self.logger.info(f"Recording: UID:{userId}    Name:{userName}")
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
        return userId

    def stop(self) -> None:
        """Stop the function from running

        Via :class:`threading.Event` to send a stop event

        Args:
            None

        Returns:
            None
        """
        self.__event.clear()
        self.logger.info("Stop fetching......")
