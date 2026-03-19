from datetime import datetime, timezone
from typing import Any, Mapping

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorCursor,
)


class MongoDBHandler:
    def __init__(
        self,
        logger,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "test",
        options: Mapping[str, Any] | None = None,
    ):
        logger.info("Initializing Database......")
        self.client = AsyncIOMotorClient(uri, **(options or {}))
        self.db = self.client[db_name]
        """
        self.backup_collection = self.db["backup"]
        self.followings_collection = self.db["All Followings"]
        self.tags_collection = self.db["All Tags"]
        self.error_collection = self.db["errors"]
        """

    def _get_collection(self, collection: str) -> AsyncIOMotorCollection:
        """
        if collection == "backup":
            return self.backup_collection
        if collection == "followings":
            return self.followings_collection
        if collection == "tags":
            return self.tags_collection
        """
        return self.db[collection]

    async def insert_one(
        self, document: dict, collection: str, backup: bool = False
    ) -> bool:
        if not isinstance(document, dict):
            raise TypeError("document must be a dict")

        result = await self._get_collection(collection).insert_one(document)
        if result.inserted_id is None:
            return False

        if backup:
            backup_data = document.copy()
            backup_data["_inserted_at"] = datetime.now(timezone.utc).isoformat()
            backup_res = await self._get_collection("backup").insert_one(backup_data)
            if backup_res.inserted_id is None:
                return False
        return True

    def find(
        self,
        key: str,
        value: Any,
        collection: str,
        projection: dict | None = None,
    ) -> AsyncIOMotorCursor:
        return self._get_collection(collection).find(
            {key: value}, projection or {"_id": 0}
        )

    async def find_one(
        self,
        key: str,
        value: Any,
        collection: str,
        includes: list[str] = [],
        excludes: list[str] = [],
    ) -> dict | None:
        projection: dict[str, int] = {"_id": 0}

        for field in includes:
            projection[field] = 1
        for field in excludes:
            projection[field] = 0

        return await self._get_collection(collection).find_one(
            {key: value},
            projection,
        )

    def find_exist(
        self,
        key: str,
        collection: str,
        includes: list[str] = [],
        excludes: list[str] = [],
    ) -> AsyncIOMotorCursor:
        projection: dict[str, int] = {"_id": 0}

        for field in includes:
            projection[field] = 1
        for field in excludes:
            projection[field] = 0

        return self._get_collection(collection).find(
            {key: {"$exists": True}},
            projection,
        )

    async def update_one(
        self,
        collection: str,
        filter: dict,
        update: dict,
        upsert: bool = False,
    ) -> int:
        result = await self._get_collection(collection).update_one(
            filter,
            update,
            upsert=upsert,
        )
        return result.modified_count

    async def set_one(
        self,
        key: str,
        value: Any,
        setter: dict,
        collection: str,
        upsert: bool = False,
    ) -> bool:
        if not isinstance(setter, dict):
            raise TypeError("setter must be a dict")

        modified_count = await self.update_one(
            collection=collection,
            filter={key: value},
            update={"$set": setter},
            upsert=upsert,
        )
        return modified_count > 0

    async def unset_one(
        self,
        key: str,
        value: Any,
        unset: str,
        collection: str,
    ) -> bool:
        modified_count = await self.update_one(
            collection=collection,
            filter={key: value},
            update={"$unset": {unset: ""}},
        )
        return modified_count > 0

    async def is_exist(self, key: str, value: Any, collection: str) -> bool:
        result = await self._get_collection(collection).find_one(
            {key: value}, {"_id": 1}
        )
        return result is not None

    async def rename_user_collection(self, collection: str, new_name: str) -> bool:
        source_collection = self._get_collection(collection)
        target_collection = self._get_collection(new_name)

        count = 0
        async for doc in source_collection.find({"id": {"$exists": True}}):
            doc["username"] = new_name
            await target_collection.insert_one(doc)
            count += 1

        if count == 0:
            return False

        if await target_collection.count_documents({"id": {"$exists": True}}) != count:
            await target_collection.drop()
            return False

        await source_collection.drop()
        return True

    async def record_error(
        self,
        error: Exception | str = "Unknown error",
        metadata: dict | None = None,
    ) -> bool:
        payload = {
            "error": str(error),
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = await self._get_collection("error").insert_one(payload)
        return result.inserted_id is not None

    async def close(self) -> None:
        self.client.close()
