import re, time
from typing import Literal
from common import ClientPool, ResponseHander, MongoDBHander
from logging import Logger


class WorkInfoRecorder:

    def __init__(
        self,
        clientpool: ClientPool,
        logger: Logger,
        mongoDb_hander: MongoDBHander,
    ):
        self.clientpool = clientpool
        self.logger = logger
        self.mongoDb_hander = mongoDb_hander

    async def record_work_info(
        self,
        work_id: str,
        work_type: Literal["illust", "novel"],
        isbookmarked: bool = False,
    ):
        """
        ## Make sure the work info is not exist before call this function.
        - manga and ugoira are included in illust.
        """
        info = await self._fetch_info(
            work_id=work_id, work_type=work_type, isbookmarked=isbookmarked
        )
        if info is None:
            return None
        if isbookmarked:
            res = await self._record_in_bookmarks(info)
            assert res, f"Record info failed.\nContent: {info}"
        else:
            # Check
            res = await self.mongoDb_hander.insert_one(
                document=info, collection=info["username"], backup=True
            )
            assert res, f"Record info failed.\nContent: {info}"

            await self._record_in_tags(info["id"], info["tags"])
            await self._record_in_user(info=info)
            # 突然意识到使用连接池的话这个就没有意义了。。。。。。
            # if info["likeData"]:
            #     await self._record_in_bookmarks(info)
        return None

    async def _fetch_info(
        self,
        work_id: str,
        work_type: Literal["illust", "novel", "series"],
        isbookmarked: bool,
    ) -> dict | None:
        """
        Get detailed information about a work.

        Example:
        ```
        {
        "type": "illust",
        "id": 126489616,
        "title": "春日ツバキ",
        "description": "",
        "tags": {
            "春日ツバキ(ガイド)": "Kasuga Tsubaki (Guide)",
            "ブルーアーカイブ": "碧蓝档案",
            "春日ツバキ": "Kasuka Tsubaki",
            "ブルアカ": null,
            "黒タイツ": "黑裤袜",
            "パンスト越しのパンツ": "隔着丝袜的内裤",
            "おっぱい": "欧派",
            "破れストッキング": "破损的丝袜",
            "眠り": "asleep",
            "ケモミミ": "兽耳"
        },
        "userId": "12870826",
        "username": "-AKOvO-",
        "uploadDate": "2025-01-23T05:09:00+00:00",
        "likeData": false,
        "likeCount": 750,
        "bookmarkCount": 1015,
        "viewCount": 3245,
        "isOriginal": false,
        "aiType": 1,
        "original_url": [
            "https://i.pximg.net/img-original/img/2025/01/23/14/09/43/126489616_p0.png"
        ],
        "relative_path": [
            "picture/12870826/126489616_p0.png"
        ]}
        """

        """
        response_hander.set_processor(
            {"SELECT": 'xpath..//meta[@id="meta-preload-data"]/@content'}
        )
        # manga and ugoira are included in illusts
        if work_type == "illust":
            '''response_hander = await self.clientpool.get(
                url="https://www.pixiv.net/artworks/" + work_id,
                response_hander=response_hander,
            )'''
            
        elif work_type == "novel":
            response_hander = await self.clientpool.get(
                url="https://www.pixiv.net/novel/show.php",
                response_hander=response_hander,
                params=[("id", work_id)],
            )
        elif work_type == "series":
            response_hander = await self.clientpool.get(
                url="https://www.pixiv.net/series/" + work_id,
                response_hander=response_hander,
                params=[("id", work_id)],
            )
        else:
            raise Exception(f"Unkonwn work type: {work_type}")
        """
        self.logger.info(f"Fetch {work_type} info......ID: {work_id}")

        # pixiv 更新接口
        if work_type == "series":
            self.logger.critical("Unused!")
            info = await self._fetch_series(work_id)
        else:
            response_hander = ResponseHander(self.logger, True)
            response_hander.set_processor({"REQUIRE": "body"})
            response_hander = await self.clientpool.get(
                url=f"https://www.pixiv.net/ajax/{work_type}/{work_id}",
                response_hander=response_hander,
                use_myclient=isbookmarked,
            )
            if isbookmarked:
                # Only use myclient, avoid being forbidden.
                time.sleep(1.5)

            if response_hander.res_code:
                self.logger.warning("Request failed.")
                if response_hander.res_code == 2:
                    await self.mongoDb_hander.record_error()
                elif response_hander.res_code == 3:
                    self.stop_all_request()
                return None

            preload_data = response_hander.processed_response
            if not isinstance(preload_data, dict):
                self.logger.warning("Load data failed.")
                return None
            info = self._parse_info(work_type, preload_data)

            work_type = info["type"]
            if (work_type == "illust") or (work_type == "manga"):
                info = await self._fetch_image_links(info)
            elif work_type == "ugoira":
                info = await self._fetch_ugoira_link(info)
            elif work_type == "novel":
                pass
            else:
                raise Exception(f"Unkonwn work type: {work_type}")

        if info is None:
            self.logger.warning(f"Fetch work info failed --- Id:{work_id}")
            return None
        # Check info
        for key, value in info.items():
            if value is None and key != "description":
                raise Exception(f"Analzey Error! ID{work_id}\n --- {info}")
        return info

    def _parse_info(
        self, work_type: Literal["illust", "novel", "series"], preload_data: dict
    ) -> dict:
        # pixiv 更新接口
        # infos = preload_data[work_type]
        # print(infos)
        _work_type: Literal["illust", "manga", "ugoira", "novel", "series"] = work_type
        self.logger.debug("Parsing work info......")
        # work_id, work_info = infos[1].popitem()

        # Common work infos
        tags: dict = {}
        for text in preload_data["tags"]["tags"]:
            tag = text["tag"]
            translation = text.get("translation")
            if translation:
                translation = translation.get("en")
            tags.update({tag: translation})

        # like?
        isliked: bool = preload_data["likeData"]
        if preload_data.get("bookmarkData") is not None:
            isliked = True

        if work_type == "illust":
            # Determine the type of work
            illust_type = preload_data["illustType"]
            if illust_type == 0:
                _work_type = "illust"
            elif illust_type == 1:
                _work_type = "manga"
            elif illust_type == 2:
                _work_type = "ugoira"
            else:
                self.logger.critical(f"Unkonwn work type: {work_type}---{illust_type}")

        if work_type == "series":
            pass

        main_info: dict = {
            "type": _work_type,
            "id": int(preload_data["id"]),
            "title": preload_data["title"],
            "description": preload_data.get("description"),
            "tags": tags,
            "userId": preload_data["userId"],
            # TODO 改为userName
            "username": preload_data["userName"],
            "uploadDate": preload_data["uploadDate"],
            "likeData": isliked,  # 是否喜欢（点赞或收藏）
            "likeCount": preload_data["likeCount"],
            "bookmarkCount": preload_data["bookmarkCount"],
            "viewCount": preload_data["viewCount"],
            "isOriginal": preload_data["isOriginal"],  # 原创作品
            "aiType": preload_data["aiType"],  # 是否使用ai
        }

        if work_type == "novel":
            # Add novel info
            main_info["content"] = preload_data.get("content")  # 小说文本
            main_info["coverUrl"] = preload_data.get("coverUrl")  # 小说封面
            main_info["characterCount"] = preload_data.get("characterCount")  # 小说字数

        return main_info

    async def _fetch_image_links(self, main_info: dict) -> dict | None:
        work_id = main_info["id"]
        xhr_url = f"https://www.pixiv.net/ajax/illust/{work_id}/pages"
        # params = {"lang": "zh"}
        # headers.update(
        #     {"referer": "https://www.pixiv.net/artworks/%d" % work_id})
        # requests = client.build_request("GET", xhr_url, params=params, headers=headers)
        # print(str(requests.url))
        response_hander = ResponseHander(self.logger, True)
        response_hander.set_processor({"REQUIRE": "body"})
        response_hander = await self.clientpool.get(
            url=xhr_url, response_hander=response_hander
        )
        if response_hander.res_code:
            self.logger.warning("Request failed.")
            if response_hander.res_code == 2:
                await self.mongoDb_hander.record_error()
            elif response_hander.res_code == 3:
                self.stop_all_request()
            return None

        body = response_hander.processed_response
        if not isinstance(body, list):
            self.logger.error("Process response failed!")
            return None
        # original image urls
        original_urls = []
        # relative path for image to save to
        relative_path = []
        for one in body:
            urls = one["urls"]
            original = urls["original"]
            name = re.search(r"[0-9]+\_.*", original)
            if name is None:
                self.logger.warning(f"Image file name not found.  ID:{work_id}")
                return None
            name = name.group()
            relative_path.append(f"picture/{main_info['userId']}/{name}")
            original_urls.append(original)
        main_info.update(
            {"original_url": original_urls, "relative_path": relative_path}
        )
        return main_info

    async def _fetch_ugoira_link(self, main_info: dict) -> dict | None:
        work_id = main_info["id"]
        xhr_url = f"https://www.pixiv.net/ajax/illust/{work_id}/ugoira_meta"
        # eg: 112392998
        # params = {"lang": "zh"}
        # headers.update(
        #     {"referer": "https://www.pixiv.net/artworks/%d" % work_id})

        response_hander = ResponseHander(self.logger, True)
        response_hander.set_processor({"REQUIRE": "body"})
        response_hander = await self.clientpool.get(
            url=xhr_url, response_hander=response_hander
        )
        if response_hander.res_code:
            self.logger.warning("Request failed.")
            if response_hander.res_code == 2:
                await self.mongoDb_hander.record_error()
            elif response_hander.res_code == 3:
                self.stop_all_request()
            return None

        body = response_hander.processed_response
        if not isinstance(body, dict):
            return None
        # original image urls
        original_urls = []
        # relative path for image to save to
        relative_path = []

        originalSrc = body["originalSrc"]
        original_urls.append(originalSrc)
        relative_path.append(f"picture/{main_info['userId']}/{work_id}.gif")
        frames = body["frames"]
        main_info.update(
            {
                "original_url": original_urls,
                "relative_path": relative_path,
                "frames": frames,
            }
        )
        return main_info

    async def _fetch_series(self, work_id: str) -> dict | None:
        # illust https://www.pixiv.net/ajax/series/156663?p=1
        # novel https://www.pixiv.net/ajax/novel/series_content/11927426?limit=30&last_order=0&order_by=asc&lang=zh
        # TODO
        page: int = 1
        params = [("p", page)]
        info = {}
        series = []
        tags = {}
        while True:
            response_hander = ResponseHander(self.logger, True)
            response_hander.set_processor({"REQUIRE": "body"})
            response_hander = await self.clientpool.get(
                url=f"https://www.pixiv.net/ajax/series/{work_id}",
                response_hander=response_hander,
                params=params,
            )

            if response_hander.res_code:
                self.logger.warning("Request failed.")
                if response_hander.res_code == 2:
                    await self.mongoDb_hander.record_error()
                elif response_hander.res_code == 3:
                    self.stop_all_request()
                return None

            body = response_hander.processed_response
            if not isinstance(body, dict):
                return None
            _series = body["page"]["series"]
            if len(_series) == 0:
                break
            series.extend(_series)

        """

        info: dict = {
            "type": "series",
            "id": int(work_id),
            "title": preload_data["title"],
            "description": preload_data.get("description"),
            "tags": tags,
            "userId": preload_data["userId"],
            # TODO 改为userName
            "username": preload_data["userName"],
            "uploadDate": preload_data["uploadDate"],
            "likeData": isliked,  # 是否喜欢（点赞或收藏）
            "likeCount": preload_data["likeCount"],
            "bookmarkCount": preload_data["bookmarkCount"],
            "viewCount": preload_data["viewCount"],
            "isOriginal": preload_data["isOriginal"],  # 原创作品
            "series": series,
        }"""

    async def _record_in_tags(self, id: int, tags: dict) -> None:
        # TODO 检查
        for name, translate in tags.items():
            earlier = await self.mongoDb_hander.find_one(
                key="name", value=name, collection="tags"
            )
            if earlier:
                workids = earlier.get("workids")
                if workids:
                    if id not in workids:
                        workids.append(id)
                else:
                    workids = [id]
                works_count = earlier.get("works_count") + 1
                earlier_translate = earlier.get("translate")
                if earlier_translate is None and translate:
                    await self.mongoDb_hander.set_one(
                        key="name",
                        value=name,
                        setter={
                            "translate": translate,
                            "works_count": works_count,
                            "workids": workids,
                        },
                        collection="tags",
                    )
                elif earlier_translate and translate:
                    if translate in earlier_translate.split("||"):
                        await self.mongoDb_hander.set_one(
                            key="name",
                            value=name,
                            setter={"works_count": works_count, "workids": workids},
                            collection="tags",
                        )
                    else:
                        await self.mongoDb_hander.set_one(
                            key="name",
                            value=name,
                            setter={
                                "translate": earlier_translate + "||" + translate,
                                "works_count": works_count,
                                "workids": workids,
                            },
                            collection="tags",
                        )
                elif (earlier_translate and translate) is None:
                    await self.mongoDb_hander.set_one(
                        key="name",
                        value=name,
                        setter={"works_count": works_count, "workids": workids},
                        collection="tags",
                    )
                else:
                    self.logger.warning(
                        "Tag translate error, not found current translate but translate has been recorded before."
                    )
                    return
            else:
                res = await self.mongoDb_hander.insert_one(
                    {
                        "name": name,
                        "translate": translate,
                        "works_count": 1,
                        "workids": [id],
                    },
                    collection="tags",
                )
                assert res, f"Record tag failed. Id:{id}"

    async def _record_in_user(self, info: dict) -> None:
        user_name = info["username"]
        userinfo = await self.mongoDb_hander.find_one(
            key="userName", value=user_name, collection="followings"
        )
        if not isinstance(userinfo, dict):
            raise Exception(f"Database Error, user not find. User name: {user_name}")
        earlier_newest_works = userinfo.get("newestWorks")
        if earlier_newest_works is None:
            assert await self.mongoDb_hander.set_one(
                key="userName",
                value=user_name,
                setter={"newestWorks": [info]},
                collection="followings",
            )
        else:
            earlier_newest_works.append(info)
            newest_works = sorted(
                earlier_newest_works, key=self._timeconverter, reverse=True
            )
            if len(newest_works) > 4:
                newest_works.pop(4)
            assert self.mongoDb_hander.set_one(
                key="userName",
                value=user_name,
                setter={"newestWorks": newest_works},
                collection="followings",
            )

    async def _record_in_bookmarks(self, info: dict) -> bool:
        not_need_backup = await self.mongoDb_hander.is_exist(
            key="id", value=int(info["id"]), collection="backup"
        )
        res = await self.mongoDb_hander.insert_one(
            document=info, collection="Bookmarks", backup=not not_need_backup
        )
        assert res, f"Record info failed.\nContent: {info}"
        return True

    def _timeconverter(self, dict_item) -> int:
        uploadDate = dict_item["uploadDate"]
        inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
        return inttime

    def stop_all_request(self) -> None:
        # TODO 
        return None


if __name__ == "__main__":
    newest_works = [
        {
            "type": "novel",
            "id": 8187018,
            "uploadDate": "2017-09-12T08:55:24+00:00",
        },
        {
            "type": "novel",
            "id": 10727287,
            "uploadDate": "2019-02-09T15:07:42+00:00",
        },
        {
            "type": "novel",
            "id": 9155342,
            "uploadDate": "2018-01-24T03:51:13+00:00",
        },
        {
            "type": "novel",
            "id": 21933141,
            "uploadDate": "2024-04-11T15:21:48+00:00",
        },
    ]

    def timeconverter(dict_item) -> int:
        uploadDate = dict_item["uploadDate"]
        inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
        return inttime

    sl = sorted(newest_works, key=timeconverter, reverse=True)
    sl.insert(0, {"fff": 555})
    sl.pop(4)
    print(sl)
    "2017-09-12T08:55:24+00:00"

"""
{
    "error": False,
    "message": "",
    "body": {
        "illustId": "123506334",
        "illustTitle": "雪風",
        "illustComment": "",
        "id": "123506334",
        "title": "雪風",
        "description": "",
        "illustType": 0,
        "createDate": "2024-10-20T03:40:00+00:00",
        "uploadDate": "2024-10-20T03:40:00+00:00",
        "restrict": 0,
        "xRestrict": 0,
        "sl": 4,
        "urls": {
            "mini": "https://i.pximg.net/c/48x48/custom-thumb/img/2024/10/20/12/40/45/123506334_p0_custom1200.jpg",
            "thumb": "https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/10/20/12/40/45/123506334_p0_custom1200.jpg",
            "small": "https://i.pximg.net/c/540x540_70/img-master/img/2024/10/20/12/40/45/123506334_p0_master1200.jpg",
            "regular": "https://i.pximg.net/img-master/img/2024/10/20/12/40/45/123506334_p0_master1200.jpg",
            "original": "https://i.pximg.net/img-original/img/2024/10/20/12/40/45/123506334_p0.jpg",
        },
        "tags": {
            "authorId": "30236169",
            "isLocked": False,
            "tags": [
                {
                    "tag": "雪風",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "yukikaze"},
                    "userName": "風神",
                },
                {
                    "tag": "戦艦少女",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "战舰少女"},
                    "userName": "風神",
                },
                {
                    "tag": "战舰少女",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "Warship Girls"},
                    "userName": "風神",
                },
                {
                    "tag": "雪風(戦艦少女)",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "userName": "風神",
                },
                {
                    "tag": "スパッツ",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "紧身裤"},
                    "userName": "風神",
                },
                {
                    "tag": "巫女",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "miko"},
                    "userName": "風神",
                },
                {
                    "tag": "お腹",
                    "locked": True,
                    "deletable": False,
                    "userId": "30236169",
                    "translation": {"en": "腹部"},
                    "userName": "風神",
                },
                {
                    "tag": "腋",
                    "locked": False,
                    "deletable": True,
                    "translation": {"en": "腋下"},
                },
                {
                    "tag": "拘束",
                    "locked": False,
                    "deletable": True,
                    "translation": {"en": "束缚"},
                },
            ],
            "writable": True,
        },
        "alt": "#雪風 雪風 - 風神的插画",
        "userId": "30236169",
        "userName": "風神",
        "userAccount": "user_fzuz2348",
        "userIllusts": {
            "128974714": None,
            "128721339": None,
            "128229846": None,
            "127980734": None,
            "127782385": None,
            "127269765": None,
            "127017262": None,
            "126779213": None,
            "126327283": None,
            "126120950": None,
            "125884718": None,
            "125625377": None,
            "125380223": None,
            "125174684": None,
            "124772565": None,
            "124346583": None,
            "124125316": None,
            "123918096": None,
            "123684724": {
                "id": "123684724",
                "title": "ソルト",
                "illustType": 0,
                "xRestrict": 1,
                "restrict": 0,
                "sl": 6,
                "url": "https://i.pximg.net/c/250x250_80_a2/img-master/img/2024/10/26/11/22/21/123684724_p0_square1200.jpg",
                "description": "",
                "tags": [
                    "R-18",
                    "maimai",
                    "猫耳",
                    "ソルト",
                    "ソルト(maimai)",
                    "抱き枕",
                    "抱き枕カバー",
                ],
                "userId": "30236169",
                "userName": "風神",
                "width": 1417,
                "height": 1417,
                "pageCount": 3,
                "isBookmarkable": True,
                "bookmarkData": None,
                "alt": "#maimai ソルト - 風神的插画",
                "titleCaptionTranslation": {"workTitle": None, "workCaption": None},
                "createDate": "2024-10-26T11:22:21+09:00",
                "updateDate": "2024-10-26T11:22:21+09:00",
                "isUnlisted": False,
                "isMasked": False,
                "aiType": 1,
                "profileImageUrl": "https://i.pximg.net/user-profile/img/2024/02/18/23/22/28/25536756_d2fc85c16590e755ce2a63b38a2c8598_50.jpg",
            },
            "123506334": {
                "id": "123506334",
                "title": "雪風",
                "illustType": 0,
                "xRestrict": 0,
                "restrict": 0,
                "sl": 4,
                "url": "https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/10/20/12/40/45/123506334_p0_custom1200.jpg",
                "description": "",
                "tags": [
                    "雪風",
                    "戦艦少女",
                    "战舰少女",
                    "雪風(戦艦少女)",
                    "スパッツ",
                    "巫女",
                    "お腹",
                    "腋",
                    "拘束",
                ],
                "userId": "30236169",
                "userName": "風神",
                "width": 2571,
                "height": 3946,
                "pageCount": 1,
                "isBookmarkable": True,
                "bookmarkData": None,
                "alt": "#雪風 雪風 - 風神的插画",
                "titleCaptionTranslation": {"workTitle": None, "workCaption": None},
                "createDate": "2024-10-20T12:40:45+09:00",
                "updateDate": "2024-10-20T12:40:45+09:00",
                "isUnlisted": False,
                "isMasked": False,
                "aiType": 1,
            },
            "123474444": {
                "id": "123474444",
                "title": "香風智乃抱き枕",
                "illustType": 0,
                "xRestrict": 1,
                "restrict": 0,
                "sl": 6,
                "url": "https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2024/10/19/14/38/09/123474444_p0_custom1200.jpg",
                "description": "",
                "tags": [
                    "R-18",
                    "香風智乃",
                    "ご注文はうさぎですか?",
                    "智乃",
                    "抱き枕カバー",
                    "抱き枕",
                    "マイクロビキニ",
                    "銀河特急ラビットハウス",
                    "おへそ",
                ],
                "userId": "30236169",
                "userName": "風神",
                "width": 2954,
                "height": 4725,
                "pageCount": 3,
                "isBookmarkable": True,
                "bookmarkData": None,
                "alt": "#香風智乃 香風智乃抱き枕 - 風神的插 画",
                "titleCaptionTranslation": {"workTitle": None, "workCaption": None},
                "createDate": "2024-10-19T14:38:09+09:00",
                "updateDate": "2024-10-19T14:38:09+09:00",
                "isUnlisted": False,
                "isMasked": False,
                "aiType": 1,
                "profileImageUrl": "https://i.pximg.net/user-profile/img/2024/02/18/23/22/28/25536756_d2fc85c16590e755ce2a63b38a2c8598_50.jpg",
            },
            "123254716": None,
            "123023491": None,
            "122838277": None,
            "122628254": None,
            "122454170": None,
            "122213309": None,
            "122037935": None,
            "121576982": None,
            "121385540": None,
            "121359447": None,
            "121171682": None,
            "121138157": None,
            "120954575": None,
            "120492655": None,
            "120290313": None,
            "119868143": None,
            "119692672": None,
            "119658798": None,
            "119452102": None,
            "119312719": None,
            "119245220": None,
            "119037518": None,
            "118830446": None,
            "118636284": None,
            "118424554": None,
            "118235918": None,
            "118007028": None,
            "117834514": None,
            "117802225": None,
            "117635022": None,
            "117418300": None,
            "117205492": None,
            "117180970": None,
            "116970995": None,
            "116762034": None,
            "116556125": None,
            "116356682": None,
            "116178138": None,
            "116142408": None,
            "115923021": None,
            "115758007": None,
            "115564450": None,
            "115526288": None,
            "115361190": None,
            "115133562": None,
            "114964557": None,
            "114939242": None,
            "114694700": None,
            "114472998": None,
            "114270521": None,
            "114083049": None,
            "113891265": None,
            "113699662": None,
            "113504205": None,
            "113324995": None,
            "113132639": None,
            "112953423": None,
            "112922087": None,
            "112758723": None,
            "112570351": None,
            "112349569": None,
            "112154841": None,
            "111966059": None,
            "111803723": None,
            "111576741": None,
            "111415790": None,
            "111067676": None,
            "110975884": None,
            "110762175": None,
            "110641619": None,
            "110587351": None,
            "110342844": None,
            "110140367": None,
            "109938695": None,
            "109733424": None,
            "109508241": None,
            "109306466": None,
            "109088374": None,
            "108890628": None,
            "108690670": None,
            "108629838": None,
            "108485784": None,
            "108292115": None,
            "108089519": None,
            "107874259": None,
            "107633547": None,
            "107413101": None,
            "107198141": None,
            "106975182": None,
            "106764373": None,
            "106545745": None,
            "106325006": None,
            "106106438": None,
            "105903512": None,
            "105702874": None,
            "105494115": None,
            "105463162": None,
            "105170360": None,
            "104991479": None,
            "104668293": None,
            "104406498": None,
            "104130766": None,
            "103937485": None,
            "103758434": None,
            "103577267": None,
            "103273549": None,
            "102956628": None,
            "102424065": None,
            "101659318": None,
            "101385166": None,
            "101082773": None,
            "100629122": None,
            "100377812": None,
            "100227402": None,
            "100156279": None,
            "100129549": None,
            "100010269": None,
            "99909023": None,
            "99520604": None,
            "99426717": None,
            "99403608": None,
            "99291934": None,
            "99028515": None,
            "98952817": None,
            "98756174": None,
            "98691126": None,
            "98594338": None,
            "98568674": None,
            "98013865": None,
            "97916328": None,
            "97777065": None,
            "97754265": None,
            "97668556": None,
            "97639899": None,
            "97262398": None,
            "97117560": None,
            "97043153": None,
            "96993896": None,
            "96810678": None,
            "96764190": None,
            "96672859": None,
            "96556402": None,
            "96530822": None,
            "96390508": None,
            "96043399": None,
            "95928675": None,
            "95807496": None,
            "95669234": None,
            "95459914": None,
            "95248097": None,
            "95135573": None,
            "95037258": None,
            "94887747": None,
            "94871569": None,
            "94578218": None,
            "93260836": None,
            "93002262": None,
            "92777613": None,
            "92573335": None,
            "92454793": None,
            "92323715": None,
            "92145703": None,
            "92028882": None,
            "92028628": None,
            "91894866": None,
            "91660928": None,
            "91660811": None,
            "91403354": None,
            "91086095": None,
            "91042668": None,
            "90982811": None,
            "90911803": None,
            "90692095": None,
            "90476416": None,
            "89968789": None,
            "89771895": None,
            "89595174": None,
            "89436042": None,
            "89320261": None,
            "89299602": None,
            "89245259": None,
            "89174089": None,
            "89047050": None,
            "88510445": None,
            "88458468": None,
            "88195138": None,
            "87709758": None,
            "87532462": None,
            "87406751": None,
            "87186298": None,
            "87097134": None,
            "86993341": None,
            "86453425": None,
            "86453378": None,
            "85887160": None,
            "85212437": None,
            "84974113": None,
            "84759065": None,
            "84758678": None,
            "84518576": None,
            "83053069": None,
            "82680558": None,
            "82405389": None,
            "81901984": None,
            "81469337": None,
            "80615247": None,
            "80170154": None,
            "78890139": None,
            "78408498": None,
            "78408108": None,
        },
        "likeData": False,
        "width": 2571,
        "height": 3946,
        "pageCount": 1,
        "bookmarkCount": 1328,
        "likeCount": 952,
        "commentCount": 4,
        "responseCount": 0,
        "viewCount": 10247,
        "bookStyle": 0,
        "isHowto": False,
        "isOriginal": False,
        "imageResponseOutData": [],
        "imageResponseData": [],
        "imageResponseCount": 0,
        "pollData": None,
        "seriesNavData": None,
        "descriptionBoothId": None,
        "descriptionYoutubeId": None,
        "comicPromotion": None,
        "fanboxPromotion": None,
        "contestBanners": [],
        "isBookmarkable": True,
        "bookmarkData": None,
        "contestData": None,
        "zoneConfig": {
            "responsive": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=illust_responsive_side&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3133"
            },
            "rectangle": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=illust_rectangle&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3977"
            },
            "500x500": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=bigbanner&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3362"
            },
            "header": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=header&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3697"
            },
            "footer": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=footer&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3196"
            },
            "expandedFooter": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=multiple_illust_viewer&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3605"
            },
            "logo": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=logo_side&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3246"
            },
            "ad_logo": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=t_logo_side&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&os=and&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3927"
            },
            "relatedworks": {
                "url": "https://pixon.ads-pixiv.net/show?zone_id=relatedworks&format=js&s=1&up=1&a=25&ng=g&sl=86&l=zh&uri=%2Fajax%2Fillust%2F_PARAM_&ref=www.pixiv.net&illust_id=123506334&K=b6fc9e32091366&D=ba3d9c132ecd8b02&ab_test_digits_first=95&yuid=JyBJN5g&num=67f1cee3677"
            },
        },
        "extraData": {
            "meta": {
                "title": "#雪風 雪風 - 風神的插画 - pixiv",
                "description": "この作品 「雪風」 は 「雪風」「戦艦少女」 等のタグがつけられた「風神」さんのイラストです。",
                "canonical": "https://www.pixiv.net/artworks/123506334",
                "alternateLanguages": {
                    "ja": "https://www.pixiv.net/artworks/123506334",
                    "en": "https://www.pixiv.net/en/artworks/123506334",
                },
                "descriptionHeader": "本作「雪風」为附有「雪風」「戦艦少女」等标签的插画。",
                "ogp": {
                    "description": "",
                    "image": "https://embed.pixiv.net/artwork.php?illust_id=123506334&mdate=1729395645",
                    "title": "#雪風 雪風 - 風神的插画 - pixiv",
                    "type": "article",
                },
                "twitter": {
                    "description": "雪風 by 風神",
                    "image": "https://embed.pixiv.net/artwork.php?illust_id=123506334&mdate=1729395645",
                    "title": "雪風",
                    "card": "summary_large_image",
                },
            }
        },
        "titleCaptionTranslation": {"workTitle": None, "workCaption": None},
        "isUnlisted": False,
        "request": None,
        "commentOff": 0,
        "aiType": 1,
        "reuploadDate": None,
        "locationMask": False,
        "commissionLinkHidden": False,
        "isLoginOnly": False,
    },
}"""
