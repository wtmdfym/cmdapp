import re
from typing import Literal, Optional
from pydantic import BaseModel, PositiveInt, NonNegativeInt
from data import SpiderResult, DBItem, Response, ParseError
from storage import DataService


class WorkInfo(BaseModel):
    type: Literal["illust", "manga", "ugoira", "novel", "series"]
    id: PositiveInt
    title: str
    description: Optional[str]
    tags: dict[str, str]
    userId: PositiveInt
    # Standardized field name for username
    userName: str
    uploadDate: str
    likeData: bool
    likeCount: PositiveInt
    bookmarkCount: PositiveInt
    viewCount: PositiveInt
    isOriginal: bool
    aiType: NonNegativeInt


def parse_info(
    work_type: Literal["illust", "novel", "series"],
    preload_data: dict,
) -> dict:
    # pixiv 更新接口
    # infos = preload_data[work_type]
    # print(infos)
    _work_type: Literal["illust", "manga", "ugoira", "novel", "series"] = work_type
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
            raise ParseError(f"Unknown work type: {work_type}---{illust_type}")

    if work_type == "series":
        pass

    # TODO work_info = WorkInfo.model_validate(preload_data)

    work_info = {
        "type": _work_type,
        "id": int(preload_data["id"]),
        "title": preload_data["title"],
        "description": preload_data.get("description"),
        "tags": tags,
        "userId": preload_data["userId"],
        # Standardized field name for username
        "userName": preload_data["userName"],
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
        work_info["content"] = preload_data["content"]  # 小说文本
        work_info["coverUrl"] = preload_data["coverUrl"]  # 小说封面
        work_info["characterCount"] = preload_data["characterCount"]  # 小说字数

    return work_info


async def parse_image_links(
    logger, dataservice: DataService, response: Response
) -> SpiderResult:
    meta = response.request.meta
    info = meta["info"]
    work_id = info["id"]
    body = response.json()["body"]
    if not isinstance(body, list):
        raise ParseError("Process response failed!")

    # original image urls
    original_urls = []
    # relative path for image to save to
    relative_path = []
    for one in body:
        urls = one["urls"]
        original = urls["original"]
        name = re.search(r"[0-9]+[\_\-]+.*", original)
        if name is None:
            raise ParseError(f"Image file name not found.  ID:{work_id}\t{one}")
        name = name.group()
        relative_path.append(f"picture/{info["userId"]}/{name}")
        original_urls.append(original)

    info.update({"original_url": original_urls, "relative_path": relative_path})

    logger.info(f"Fetch {info["type"]}---{work_id} info complete.")

    if info["likeData"]:
        return SpiderResult(
            items=[
                await dataservice.record_in_bookmarks(info),
                # await dataservice.record_in_user(info),
            ]
        )
    else:
        return SpiderResult(
            items=[
                await dataservice.record_in_user(info),
                DBItem(
                    collection="works",
                    backup=True,
                    op="insert",
                    document=info,
                ),
            ]
        )


async def parse_ugoira_link(logger, dataservice, response: Response) -> SpiderResult:
    meta = response.request.meta
    info = meta["info"]
    work_id = info["id"]

    body = response.json()["body"]
    if not isinstance(body, dict):
        raise ParseError("Ugoira image link")

    # original image urls
    original_urls = []
    # relative path for image to save to
    relative_path = []

    originalSrc = body["originalSrc"]
    original_urls.append(originalSrc)
    relative_path.append(f"picture/{info["userId"]}/{work_id}.gif")
    frames = body["frames"]
    info.update(
        {
            "original_url": original_urls,
            "relative_path": relative_path,
            "frames": frames,
        }
    )

    logger.info(f"Fetch {info["type"]}---{work_id} info complete.")

    if info["likeData"]:
        return SpiderResult(
            items=[
                await dataservice.record_in_bookmarks(info),
                # await dataservice.record_in_user(info),
            ]
        )
    else:
        return SpiderResult(
            items=[
                await dataservice.record_in_user(info),
                DBItem(
                    collection="works",
                    backup=True,
                    op="insert",
                    document=info,
                ),
            ]
        )


def timeconverter(dict_item) -> int:
    uploadDate = dict_item["uploadDate"]
    inttime = int(uploadDate[0:4] + uploadDate[5:7] + uploadDate[8:10])
    return inttime
