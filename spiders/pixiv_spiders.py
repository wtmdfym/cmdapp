from .pixiv import FollowingInfoSpider, WorkInfoSpider, BookmarkWorkSpider
from .base_spider import SpiderCollection


class PixivSpiders(SpiderCollection):
    name = "pixiv"
    _spiders = set([FollowingInfoSpider, WorkInfoSpider, BookmarkWorkSpider])
