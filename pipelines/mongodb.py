from data import SpiderResult
from storage import MongoDBHandler


class MongoDBPipeline:

    def __init__(self, logger):
        self.mongo = MongoDBHandler(logger)

    async def process_item(self, result: SpiderResult) -> bool:
        data = result.db_data
        if data is None:
            return False

        try:
            collection = data.pop("collection")
            backup = data.pop("backup")
        except KeyError:
            return False

        return await self.mongo.insert_one(
            document=data,
            collection=collection,
            backup=backup,
        )
