from dataclasses import dataclass, replace, field
from typing import Callable, Any
from hashlib import sha1
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from httpx import AsyncClient
from enum import Enum


class AccountStatus(Enum):
    HEALTHY = "healthy"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"


class EngineStatus(Enum):
    STOP = "stop"
    RUNNING = "running"
    PAUSE = "pause"


@dataclass
class SpiderResult:
    requests: list[Request] = field(default_factory=list)
    db_data: dict[str, Any] | None = None
    raw_data: str = ""


@dataclass
class PixivAccount:
    email: str
    cookies: dict
    client: AsyncClient
    last_request_time: float
    cooldown_until: float = 0
    status: AccountStatus = AccountStatus.HEALTHY
    fail_count: int = 0


Callback = Callable[["Response"], SpiderResult]
Errback = Callable[["Request", Exception], Any]


@dataclass(slots=True)
class Request:
    method: str
    url: str
    callback: Callback

    # HTTP
    params: dict | None = None
    data: dict | None = None
    headers: dict | None = None

    # 调度相关
    priority: int = 20  # 0-100
    use_primary: bool = False

    # 重试
    retry_times: int = 0
    max_retry: int = 3

    meta: dict = field(default_factory=dict)

    errback: Errback | None = None

    @property
    def fingerprint(self) -> bytes:
        """
        Generate a request fingerprint for deduplication.

         - Includes: Request method + Canonical URL + Request body data
         - Excludes: Scheduling-related fields, such as priority, use_primary, and retry_times
        """
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
        return sha1(fp_str.encode("utf-8")).digest()

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
