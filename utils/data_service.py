from storage import MongoDBHandler


class DataService:
    """
    Read Only
    """

    def __init__(self, mongo: MongoDBHandler):
        self.mongo = mongo

    def following_users(self):
        return self.mongo.find_exist(
            "userId",
            "followings",
            excludes=["userComment", "profileImageUrl", "newestWorks"],
        )

    async def user_info(self, user_id: str):
        return await self.mongo.find_one(
            "userId",
            user_id,
            "followings",
            excludes=["newestWorks"],
        )
