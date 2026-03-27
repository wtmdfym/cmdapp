from .mongoDB_handler import MongoDBHandler
from data import BaseItem, DBItem, ParseError


class DataService:
    """
    Read Only
    """

    def __init__(self, mongo: MongoDBHandler):
        self._mongo = mongo

    def following_users(self):
        return self._mongo.find_exist(
            "userId",
            "followings",
            excludes={"userComment", "profileImageUrl", "newestWorks"},
        )

    async def user_info(self, user_id: str):
        return await self._mongo.find_one(
            "userId",
            user_id,
            "followings",
            excludes={"newestWorks"},
        )

    async def check_exist_work(self, work_id: str) -> bool:
        return await self._mongo.is_exist("id", int(work_id), "works")

    async def check_exist_works(self, work_ids: set[str]) -> set[str]:
        async for work_id in self._mongo.find_exist("id", "works", includes={"id"}):
            work_ids.discard(str(work_id["id"]))
        return work_ids

    async def check_exist_works2(self, work_ids: set[str]) -> set[str]:
        for work_id in work_ids.copy():
            if await self._mongo.is_exist("id", int(work_id), "works"):
                work_ids.discard(str(work_id))
        return work_ids

    async def record_in_tags(self, id: int, tags: dict[str, str]):

        for name, translate in tags.items():
            earlier = await self._mongo.find_one(
                key="name",
                value=name,
                collection="tags",
            )

            if earlier:
                workids = earlier["workids"]
                if id not in workids:
                    workids.append(id)

                works_count = earlier["works_count"] + 1
                setter = {"works_count": works_count, "workids": workids}
                earlier_translate = earlier.get("translate")

                if translate:
                    if earlier_translate:
                        if not translate in earlier_translate.split("||"):
                            setter["translate"] = earlier_translate + "||" + translate
                    else:
                        setter["translate"] = translate

                # if earlier_translate:
                #     raise ParseError(
                #         "Tag translate error, not found current translate but translate has been recorded before.",
                #         tags,
                #         name,
                #     )

                yield DBItem(
                    collection="tags",
                    backup=False,
                    op="update",
                    update_filter={"name": name},
                    update={"$set": setter},
                )

            else:
                yield DBItem(
                    collection="tags",
                    backup=False,
                    op="insert",
                    document={
                        "name": name,
                        "translate": translate,
                        "works_count": 1,
                        "workids": [id],
                    },
                )

    async def record_in_user(self, info: dict) -> BaseItem:
        user_name = info["userName"]
        userinfo = await self._mongo.find_one(
            key="userName", value=user_name, collection="followings"
        )
        if not isinstance(userinfo, dict):
            raise Exception(
                f"Database Error, user not find. User name: {user_name}",
                info,
            )
        earlier_newest_works = userinfo.get("newestWorks")
        if earlier_newest_works is None:
            return DBItem(
                collection="followings",
                backup=False,
                op="update",
                update_filter={"userName": user_name},
                update={"$set": {"newestWorks": [info]}},
            )

        else:
            earlier_newest_works.append(info)
            newest_works = sorted(earlier_newest_works, key=timeconverter, reverse=True)
            if len(newest_works) > 4:
                newest_works.pop(4)
            return DBItem(
                collection="followings",
                backup=False,
                op="update",
                update_filter={"userName": user_name},
                update={"$set": {"newestWorks": newest_works}},
            )

    async def record_in_bookmarks(self, info: dict) -> BaseItem:
        not_need_backup = await self._mongo.is_exist(
            key="id", value=int(info["id"]), collection="backup"
        )
        return DBItem(
            collection="bookmarks",
            backup=not not_need_backup,
            op="insert",
            document=info,
        )


def timeconverter(dict_item) -> int:
    uploadDate = dict_item["uploadDate"]
    inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
    return inttime
