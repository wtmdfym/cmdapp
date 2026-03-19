from .base import BasePipeline
from storage import MongoDBHandler


class MongoDBPipeline(BasePipeline):
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

    async def _process_item(self, item: dict) -> bool:

        item = item.copy()
        try:
            collection = item["collection"]
            backup = item["backup"]
            operation = item["op"]
        except KeyError:
            self.logger.warning("Invalid item format.")
            return False

        if operation == "insert":
            self.logger.debug(f"MongoDB insert:\n\t{item["document"]}")
            return await self.mongo.insert_one(
                document=item["document"],
                collection=collection,
                backup=backup,
            )

        elif operation == "update":
            self.logger.debug(
                f"""MongoDB update:\t
                filter --- {item["filter"]}\t
                update --- {item["update"]}"""
            )
            return (
                await self.mongo.update_one(
                    collection=collection,
                    filter=item["filter"],
                    update=item["update"],
                )
                > 0
            )

        elif operation == "rename":
            self.logger.debug(
                f"MongoDB rename:\n\t{collection} ---> {item["new_name"]}"
            )
            return await self.mongo.rename_user_collection(
                collection=collection,
                new_name=item["new_name"],
            )

        else:
            raise ValueError(f"Invalid operation: {operation}")
