from data import Request, Response, SpiderResult, ParseError
from utils import ConfigManager
from storage import DataService

from ..base_spider import BaseSpider
from .tools import parse_info, parse_image_links, parse_ugoira_link


class WorkInfoSpider(BaseSpider):
    name = "workinfo"
    registry = {"db": "mongodb"}

    def __init__(self, logger, config: ConfigManager, dataservice: DataService):
        super().__init__(logger)
        self.myId = config.require("clientpool_config.primary_account.id")
        self.dataservice = dataservice
        self.init_requests = []
        self.download_type = {"illust", "manga", "novels", "series"}

    async def start(self) -> list[Request]:
        _followings = self.dataservice.following_users()
        async for following in _followings:
            if following.get("not_following_now"):
                continue

            user_id = following["userId"]
            user_name = following["userName"]
            self.init_requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/user/{user_id}/profile/all",
                    spider_parser=self._parse_work_id,
                    headers={"referer": f"https://www.pixiv.net/users/{user_id}"},
                    params={"lang": "zh"},
                    priority=50,
                    meta={"uid": user_id, "name": user_name},
                )
            )
            break
        return await super().start()

    async def _parse_work_id(self, response: Response) -> SpiderResult:
        """fetch and record all works'info of the following user"""
        meta = response.request.meta
        user_id = meta["uid"]
        user_name = meta["name"]
        self.logger.info(
            f"Fetch works'information for user {user_name}---{user_id} ..."
        )
        body = response.json()["body"]

        if not isinstance(body, dict):
            raise ParseError(
                f"Parse work id failed User: {user_name}---{user_id}\nResponse: {response.text()}"
            )

        spider_result = SpiderResult()
        work_ids = set[str]()

        if "illust" in self.download_type:
            illust_ids = body.get("illusts")
            if isinstance(illust_ids, dict):
                illust_ids = set(illust_ids)
                work_ids = await self.dataservice.check_exist_works(illust_ids)
                self.logger.debug(f"Skip exist works: {illust_ids-work_ids}")

            elif isinstance(illust_ids, list) and (len(illust_ids) == 0):
                pass
            else:
                raise ParseError("Illusts parse method error")

        if "manga" in self.download_type:
            manga_ids = body.get("manga")
            if isinstance(manga_ids, dict):
                manga_ids = set(manga_ids)
                manga_ids = await self.dataservice.check_exist_works(manga_ids)
                self.logger.debug(f"Skip exist works: {manga_ids-work_ids}")
                work_ids = work_ids | manga_ids
            elif isinstance(manga_ids, list) and (len(manga_ids) == 0):
                pass
            else:
                raise ParseError("Manga parse method error")

        for illust_id in work_ids:

            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/illust/{illust_id}",
                    spider_parser=self._parse_work_info,
                    headers={"referer": f"https://www.pixiv.net/users/{user_id}"},
                    params={"lang": "zh"},
                    priority=40,
                    meta={"work_id": illust_id, "work_type": "illust"},
                )
            )

        if "novels" in self.download_type:
            novels_ids = body.get("novels")
            if isinstance(novels_ids, dict):
                novels_ids = set(novels_ids)
                novels_ids = await self.dataservice.check_exist_works(novels_ids)
                self.logger.debug(f"Skip exist works: {novels_ids-work_ids}")
                for novel_id in novels_ids:

                    spider_result.requests.append(
                        Request(
                            "GET",
                            f"https://www.pixiv.net/ajax/novel/{novel_id}",
                            spider_parser=self._parse_work_info,
                            headers={
                                "referer": f"https://www.pixiv.net/users/{user_id}"
                            },
                            params={"lang": "zh"},
                            priority=40,
                            meta={"work_id": novel_id, "work_type": "novels"},
                        )
                    )
            elif isinstance(novels_ids, list) and (len(novels_ids) == 0):
                pass
            else:
                raise ParseError("Novels parse method error")

        if "series" in self.download_type:
            mangaSeries = body.get("mangaSeries")
            if not isinstance(mangaSeries, list):
                raise ParseError
            """
            {
                "id": "192908",
                "userId": "34217753",
                "title": "爱丽丝和A的同居日常",
                "description": "我和A老师的同居日常。（事实上我们并没有在同居）",
                "caption": "我和A老师的同居日常。（事实上我们并没有在同居）",
                "total": 2,
                "content_order": null,
                "url": "https://i.pximg.net/c/782x410_80_a2_g2/img-master/img/2023/03/29/23/56/55/106680718_p0_master1200.jpg",
                "coverImageSl": 6,
                "firstIllustId": "106679172",
                "latestIllustId": "106680718",
                "createDate": "2023-03-29T23:11:58+09:00",
                "updateDate": "2023-03-29T23:56:57+09:00",
                "watchCount": null,
                "isWatched": false,
                "isNotifying": false
            },
            {
                "id": "10578072",
                "userId": "34217753",
                "userName": "BobAlice",
                "profileImageUrl": "https://i.pximg.net/user-profile/img/2022/10/10/21/31/53/23445849_1f342e895f4316553fbe6626e038f12e_170.png",
                "xRestrict": 1,
                "isOriginal": true,
                "isConcluded": false,
                "genreId": "4",
                "title": "赌城",
                "caption": "爱丽丝与琳是一对职业赌徒搭档，过去她们在赌城战无不胜。但是这次，她们的好运似乎到头了。因为爱丽丝赌马欠下巨债的她们被辛迪加绑架，即将被强迫卖身。但幸运的是，在她们面前还有一个重获自由的机会……前提是：她们能够在接下来的一场场赌局中赢到最后……",
                "language": "ja",
                "tags": [
                    "中文",
                    "剧情",
                    "拘束",
                    "DID",
                    "捆绑",
                    "紧缚",
                    "绑架",
                    "赌博",
                    "智斗"
                ],
                "publishedContentCount": 3,
                "publishedTotalCharacterCount": 18129,
                "publishedTotalWordCount": 9760,
                "publishedReadingTime": 2719,
                "useWordCount": false,
                "lastPublishedContentTimestamp": 1718890595,
                "createdTimestamp": 1686565754,
                "updatedTimestamp": 1718893409,
                "createDate": "2023-06-12T19:29:14+09:00",
                "updateDate": "2024-06-20T23:23:29+09:00",
                "firstNovelId": "20063883",
                "latestNovelId": "22402834",
                "displaySeriesContentCount": 3,
                "shareText": "[R-18] 赌城 | BobAlice #pixiv",
                "total": 3,
                "firstEpisode": {
                    "url": "https://i.pximg.net/c/600x600/novel-cover-master/img/2023/07/09/02/36/35/ci20063883_a319d7e57e14b50c078d6bfc6d051410_master1200.jpg"
                },
                "watchCount": null,
                "maxXRestrict": null,
                "cover": {
                    "urls": {
                        "240mw": "https://i.pximg.net/c/240x480_80/novel-cover-master/img/2023/06/12/19/39/01/sci10578072_39ac2d0b51f717998192cd0969620a62_master1200.jpg",
                        "480mw": "https://i.pximg.net/c/480x960/novel-cover-master/img/2023/06/12/19/39/01/sci10578072_39ac2d0b51f717998192cd0969620a62_master1200.jpg",
                        "1200x1200": "https://i.pximg.net/c/1200x1200/novel-cover-master/img/2023/06/12/19/39/01/sci10578072_39ac2d0b51f717998192cd0969620a62_master1200.jpg",
                        "128x128": "https://i.pximg.net/c/128x128/novel-cover-master/img/2023/06/12/19/39/01/sci10578072_39ac2d0b51f717998192cd0969620a62_square1200.jpg",
                        "original": "https://i.pximg.net/novel-cover-original/img/2023/06/12/19/39/01/sci10578072_39ac2d0b51f717998192cd0969620a62.png"
                    }
                },
                "coverSettingData": null,
                "isWatched": false,
                "isNotifying": false,
                "aiType": 1
            },
            """
            # for mangaSerie in mangaSeries:
            # spider_result.requests.append(
            #     Request(
            #         "GET",
            #         f"https://www.pixiv.net/ajax/series/{mangaSerie["id"]}?p=1",
            #         spider_parser=self._fetch_series,
            #         headers={"referer": f"https://www.pixiv.net/users/{user_id}"},
            #         params={"lang": "zh", "p": 1},
            #         priority=25,
            #         meta={"series_info": mangaSerie, "p": 1},
            #     )
            # )
            novelSeries = body.get("novelSeries")

        self.logger.info(
            f"Fetch works'information for user {user_name}---{user_id} complete."
        )

        return spider_result

    async def _parse_work_info(self, response: Response) -> SpiderResult:
        meta = response.request.meta
        work_id = meta["work_id"]
        work_type = meta["work_type"]
        self.logger.info(f"Fetch {work_type}---{work_id} info")
        spider_result = SpiderResult()

        # pixiv 更新接口
        if work_type == "series":
            raise ParseError("Unused!")
            # info = await self._fetch_series(work_id)

        preload_data = response.json()["body"]
        if not isinstance(preload_data, dict):
            raise ParseError("Load data failed.")

        info = parse_info(work_type, preload_data)

        work_type = info["type"]
        if (work_type == "illust") or (work_type == "manga"):
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/illust/{work_id}/pages",
                    spider_parser=lambda res: parse_image_links(
                        self.logger,
                        self.dataservice,
                        res,
                    ),
                    headers={"referer": f"https://www.pixiv.net/artworks/{work_id}"},
                    params={"lang": "zh"},
                    priority=30,
                    meta={"info": info},
                )
            )
        elif work_type == "ugoira":
            spider_result.requests.append(
                Request(
                    "GET",
                    f"https://www.pixiv.net/ajax/illust/{work_id}/ugoira_meta",
                    spider_parser=lambda res: parse_ugoira_link(
                        self.logger,
                        self.dataservice,
                        res,
                    ),
                    headers={"referer": f"https://www.pixiv.net/artworks/{work_id}"},
                    params={"lang": "zh"},
                    priority=30,
                    meta={"info": info},
                )
            )
        elif work_type == "novel":
            pass
        else:
            raise ParseError(f"Unknown work type: {work_type}")

        async for item in self.dataservice.record_in_tags(
            id=int(work_id),
            tags=info["tags"],
        ):
            spider_result.items.append(item)

        return spider_result


'''
    async def _fetch_series(self, response: Response) -> SpiderResult:
        """
        Fetch series information from Pixiv API.
        Series structure: illusts and novels can be part of a series.
        - illust: https://www.pixiv.net/ajax/series/{work_id}?p=1
        - novel: https://www.pixiv.net/ajax/novel/series_content/{work_id}?limit=30&last_order=0&order_by=asc&lang=zh
        """
        page: int = 1
        params = [("p", page)]
        series_data = []

        while True:
            response_hander = ResponseHander(self.logger, True)
            response_hander.set_processor({"REQUIRE": "body"})
            response_hander = await self.clientpool.get(
                url=f"https://www.pixiv.net/ajax/series/{work_id}",
                response_hander=response_hander,
                params=params,
            )

            body = response.json()["body"]
            if not isinstance(body, dict):
                self.logger.error(f"Invalid response format for series {work_id}")
                return None
            _series = body["page"]["series"]
            if len(_series) == 0:
                break
            series_data.extend(_series)
            page += 1
            params = [("p", page)]

        # Series support is currently not implemented for full data structure
        self.logger.debug(f"Fetched {len(series_data)} series items for work {work_id}")
        return None  # Series recording not yet fully implemented

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
'''
