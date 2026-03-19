from .base_spider import BaseSpider
from data import Request, Response, SpiderResult, ParseError, Item
from utils import ConfigHandler, DataService


class FollowingInfoSpider(BaseSpider):
    name = "followinginfo"
    registry = {"db": "mongodb"}

    def __init__(self, logger, config: ConfigHandler, dataservice: DataService):
        super().__init__(logger)
        self.myId = config.require("clientpool_config.primary_account.id")
        self.dataservice = dataservice
        self.init_requests = [
            Request(
                "GET",
                "https://www.pixiv.net/ajax/user/extra",
                spider_parser=self._parse_followings_count,
                headers={
                    "referer": f"https://www.pixiv.net/users/{self.myId}/following?p=1"
                },
                use_primary=True,
                priority=10,
            )
        ]

    async def _parse_followings_count(self, response: Response) -> SpiderResult:
        try:
            res = response.json()
            following = res["body"]["following"]
            if not isinstance(following, int):
                raise ParseError("Following count not find.")
        except KeyError as e:
            self.logger.exception(e)
            return SpiderResult(self.init_requests)
        except ParseError as e:
            self.logger.exception(e)
            return SpiderResult()

        # self.logger.debug(following)

        following_url = f"https://www.pixiv.net/ajax/user/{self.myId}/following"
        all_page = (following + 23) // 24
        if all_page <= 0:
            return SpiderResult()

        return SpiderResult(
            requests=[
                Request(
                    "GET",
                    following_url,
                    self._parse_followings_id,
                    params={
                        "offset": 0,
                        "limit": 24,
                        "rest": "show",
                        "tag": None,
                        "acceptingRequests": 0,
                        "lang": "zh",
                    },
                    use_primary=True,
                    priority=21,
                    meta={
                        "page": 0,
                        "all_page": all_page,
                        "following_user_ids": [],
                    },
                )
            ]
        )

    async def _parse_followings_id(self, response: Response) -> SpiderResult:
        spider_result = SpiderResult()

        try:
            res = response.json()
            users = res["body"]["users"]
            if not isinstance(users, list):
                raise ParseError("User ID list not find.")
        except KeyError as e:
            self.logger.exception(e)
            return SpiderResult(self.init_requests)
        except ParseError as e:
            self.logger.exception(e)
            return spider_result

        request_meta = response.request.meta or {}
        page = request_meta.get("page", 0)
        all_page = request_meta.get("all_page", 1)
        user_id_set = set(request_meta.get("following_user_ids", []))

        self.logger.info(
            f"Updating following user info...... page={page + 1}/{all_page}"
        )

        for user in users:
            if not isinstance(user, dict):
                raise ParseError("User data not find.")
            user_id_set.add(user["userId"])

            async for item in self._update_following_info(user):
                if item:
                    spider_result.items.append(item)

        # 逐页请求，最后一页时再计算未关注
        if page + 1 < all_page:
            next_page = page + 1
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/user/{self.myId}/following",
                    self._parse_followings_id,
                    params={
                        "offset": next_page * 24,
                        "limit": 24,
                        "rest": "show",
                        "tag": None,
                        "acceptingRequests": 0,
                        "lang": "zh",
                    },
                    use_primary=True,
                    priority=21,
                    meta={
                        "page": next_page,
                        "all_page": all_page,
                        "following_user_ids": list(user_id_set),
                    },
                )
            )
            return spider_result

        # 最后一页时，才将数据库中当前已同意关注的用户标记为 not_following_now
        async for following in self.dataservice.following_users():
            user_id = following["userId"]
            if user_id in user_id_set:
                continue
            if following.get("not_following_now"):
                continue

            self.logger.warning(f"Not following now: {following}")
            spider_result.items.append(
                Item(
                    type="db",
                    data={
                        "collection": "followings",
                        "backup": False,
                        "op": "update",
                        "filter": {"userId": following["userId"]},
                        "update": {
                            "$set": {"not_following_now": True},
                        },
                    },
                )
            )

        return spider_result

    async def _update_following_info(self, following_info: dict):
        user_id = following_info["userId"]
        # Skip Pixiv official account
        if user_id == "11":
            yield None
            return
        userName = following_info["userName"]  # make sure it exist
        userComment = following_info.get("userComment")
        profileImageUrl = following_info.get("profileImageUrl")

        earlier = await self.dataservice.user_info(user_id)
        if earlier is None:
            self.logger.info(f"Recording: UID:{user_id}    Name:{userName}")
            yield Item(
                type="db",
                data={
                    "collection": "followings",
                    "backup": False,
                    "op": "insert",
                    "document": {
                        "userId": user_id,
                        "userName": userName,
                        "userComment": userComment,
                        "profileImageUrl": profileImageUrl,
                    },
                },
            )
            return

        self.logger.debug(f"Have been recorded: UID: {user_id}   Name: {userName}")
        setter = {}
        unsetter = {}

        earlier_userName = earlier["userName"]

        if earlier_userName != userName:
            yield Item(
                type="db",
                data={
                    "collection": earlier_userName,
                    "backup": False,
                    "op": "rename",
                    "new_name": userName,
                },
            )
            setter["userName"] = userName

        if earlier.get("userComment") != userComment:
            setter["userComment"] = userComment

        if earlier.get("profileImageUrl") != profileImageUrl:
            setter["profileImageUrl"] = profileImageUrl

        if earlier.get("not_following_now"):
            unsetter["not_following_now"] = ""
            self.logger.info(f"Following again: {userName} --- {user_id}")

        if (len(setter) > 0) or (len(unsetter) > 0):
            self.logger.debug(
                f"Updating user info: set --- {setter}|unset --- {unsetter}."
            )
            yield Item(
                type="db",
                data={
                    "collection": "followings",
                    "backup": False,
                    "op": "update",
                    "filter": {"userId": user_id},
                    "update": {
                        "$set": setter,
                        "$unset": unsetter,
                    },
                },
            )
