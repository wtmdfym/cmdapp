from logging import Logger
from motor.motor_asyncio import *
import asyncio


class MongoDBHander:
    def __init__(self, logger: Logger, loop: asyncio.AbstractEventLoop):
        # 初始化数据库
        logger.info("初始化数据库......")
        client = AsyncIOMotorClient("localhost", 27017, io_loop=loop)
        self.db = client["pixiv"]
        self.backup_collection = client["backup"]["backup of pixiv infos"]
        self.followings_collection = self.db["All Followings"]
        self.tags_collection = self.db["All Tags"]

    def _get_collection(self, collection: str) -> AsyncIOMotorCollection:
        if collection == "backup":
            return self.backup_collection
        elif collection == "followings":
            return self.followings_collection
        elif collection == "tags":
            return self.tags_collection
        else:
            return self.db[collection]

    async def insert_one(self, document, collection: str, backup: bool = False) -> bool:
        result = await self._get_collection(collection).insert_one(document=document)
        if not result:
            return False
        if backup:
            result = await self._get_collection("backup").insert_one(document=document)
            if not result:
                return False
        return True

    def find(self, key: str, value, collection: str) -> AsyncIOMotorCursor:
        return self._get_collection(collection).find({key: value}, {"_id": 0})

    def find_one(self, key: str, value, collection: str):
        return self._get_collection(collection).find_one({key: value}, {"_id": 0})

    def find_exist(self, key: str, collection: str) -> AsyncIOMotorCursor:
        return self._get_collection(collection).find(
            {key: {"$exists": "true"}}, {"_id": 0}
        )

    def set_one(self, key: str, value, setter: dict, collection: str):
        return self._get_collection(collection).update_one(
            {key: value}, {"$set": setter}
        )

    def unset_one(self, key: str, value, unset: str, collection: str):
        return self._get_collection(collection).update_one(
            {key: value}, {"$unset": {unset: ""}}
        )

    async def is_exist(self, key: str, value, collection: str) -> bool:
        result = await self._get_collection(collection).find_one(
            {key: value}, {"_id": 1}
        )
        return result is not None

    async def rename_user_collection(self, collection: str, new_name: str):
        collection_1 = self.db[collection]
        collection_2 = self.db[new_name]
        async for doc in collection_1.find({"id": {"$exists": True}}):
            doc.update({"username": new_name})
            await collection_2.insert_one(doc)
        await collection_1.drop()

    async def mongoDB_auto_backup(self) -> bool:
        # Dont need
        return True
        self.logger.info("开始自动备份,请勿关闭程序!!!")
        names = await self.db.list_collection_names()
        for name in names:
            collection = self.db[name]
            # 可不用
            async with self.semaphore:
                async for docs in collection.find(
                    {"id": {"$exists": True}}, {"_id": 0}
                ):
                    if not self.__event.is_set():
                        self.logger.info("停止自动备份!")
                        return False
                    if len(docs) >= 9:
                        b = await self.backup_collection.find_one(
                            {"id": docs.get("id")}
                        )
                        if b:
                            continue
                        else:
                            await self.backup_collection.insert_one(docs)
                            # print(c)
        self.logger.info("自动备份完成!")
        return True