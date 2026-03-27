from dataclasses import dataclass, replace, field
from typing import Callable, Any, Iterator, Awaitable
from hashlib import md5
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from httpx import AsyncClient
from enum import Enum

from .items import BaseItem


class AccountStatus(Enum):
    HEALTHY = "healthy"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    # USING = "using"


class SpiderStatus(Enum):
    WAIT = "wait"
    RUNNING = "running"
    FINISH = "finish"


class EngineStatus(Enum):
    STOP = "stop"
    RUNNING = "running"
    PAUSE = "pause"


# @dataclass(slots=True)
# class Item:
#     type: str  # 数据类型（核心）
#     data: dict[str, Any]  # 业务数据
# meta: dict[str, Any] = field(default_factory=dict)  # 可选扩展


@dataclass
class SpiderResult:
    """
    item_example:
    {"name": "The name of pipeline",
    "data": "Any data the target pipeline can process"}
    """

    requests: list[Request] = field(default_factory=list)
    # TODO requests: Iterator[Request] = field(default_factory=Iterator)
    items: list[BaseItem] = field(default_factory=list)


@dataclass
class PixivAccount:
    email: str
    cookies: dict
    client: AsyncClient
    last_request_time: float
    wait_until: float = 0
    status: AccountStatus = AccountStatus.HEALTHY
    fail_count: int = 0


Callback = Callable[["Response"], Awaitable[SpiderResult]]
Errback = Callable[["Request", Exception], Any]


@dataclass(slots=True)
class Request:
    method: str
    url: str
    spider_parser: Callback

    # HTTP
    params: dict | None = None
    data: dict | None = None
    headers: dict | None = None

    # 调度相关
    priority: int = 50  # 0-100
    use_primary: bool = False

    # 重试
    retry_times: int = 0
    max_retry: int = 3
    ignore: bool = False

    meta: dict = field(default_factory=dict)

    errback: Errback | None = None
    # Cache fingerpoint
    _fingerprint: bytes | None = None

    @property
    def fingerprint(self) -> bytes:
        """
        Generate a request fingerprint for deduplication.

         - Includes: Request method + Canonical URL + Request body data
         - Excludes: Scheduling-related fields, such as priority, use_primary, and retry_times
        """
        if self._fingerprint:
            return self._fingerprint

        # 规范化URL（排序query参数，去除fragment）
        parsed = urlparse(self.url)

        # 合并URL中的query参数和self.params
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        if self.params:
            for k, v in self.params.items():
                query_params[k] = [v] if not isinstance(v, list) else v

        # 排序并编码query参数
        sorted_query = []
        for k in sorted(query_params.keys()):
            for v in sorted(query_params[k]):
                sorted_query.append((k, v))

        normalized_url = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),  # 域名统一小写
                parsed.path,
                parsed.params,
                urlencode(sorted_query, doseq=True),
                "",  # 移除fragment，避免锚点影响去重
            )
        )

        # 构建指纹内容
        fp_parts = [self.method.upper(), normalized_url]

        # 包含body数据（如果有）
        if self.data:
            if isinstance(self.data, dict):
                # 排序data字段，确保一致性
                fp_parts.append(urlencode(sorted(self.data.items())))
            else:
                fp_parts.append(str(self.data))

        fp_str = "|".join(fp_parts)
        self._fingerprint = md5(fp_str.encode("utf-8")).digest()
        return self._fingerprint

    def copy(self, **kwargs) -> "Request":
        return replace(self, **kwargs)

    def next_retry(self) -> "Request":
        return replace(self, retry_times=self.retry_times + 1)


@dataclass(slots=True)
class Response:
    request: Request
    status: int
    headers: dict
    content: bytes
    elapsed: float
    raw: Any  # httpx.Response

    def text(self) -> str:
        return self.content.decode(errors="ignore")

    def json(self) -> Any:
        return self.raw.json()

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_rate_limited(self) -> bool:
        return self.status == 429

    @property
    def is_auth_error(self) -> bool:
        return self.status in (401, 403)


class ParseError(RuntimeError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
