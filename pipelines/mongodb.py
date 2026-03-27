from data import DBItem
from storage import MongoDBHandler

from .base import BasePipeline


class MongoDBPipeline(BasePipeline[DBItem]):
    """
    Data format:{
        "collection": "collection_name",
        "backup": True, If True, the document will be backed up before insertion.
        "op": "insert/update/rename..."
        ... other fields to be process with the document ...
        }

    op example:
        insert:
            "document": {Any}
        update:
            "filter": {"userId": user_id},
            "update": {"$set": {"name": name}}
        rename:
            "new_name": "name"
    """

    name = "mongodb"

    def __init__(self, logger, mongo: MongoDBHandler):
        self.logger = logger
        self.mongo = mongo

    async def _process_item(self, item: DBItem) -> bool:

        if item.op == "insert":
            self.logger.debug(f"MongoDB insert:\n\t{item.document}")
            return await self.mongo.insert_one(
                document=item.document,  # type: ignore
                collection=item.collection,
                backup=item.backup,
            )

        if item.op == "update":
            self.logger.debug(
                f"""MongoDB update:\t
                filter --- {item.update_filter}\t
                update --- {item.update}"""
            )
            return (
                await self.mongo.update_one(
                    collection=item.collection,
                    filter=item.update_filter,  # type: ignore
                    update=item.update,  # type: ignore
                )
                > 0
            )

        if item.op == "rename":
            self.logger.debug(
                f"MongoDB rename:\n\t{item.collection} ---> {item.new_name}"
            )
            return await self.mongo.rename_user_collection(
                collection=item.collection,
                new_name=item.new_name,  # type: ignore
            )

        return False
