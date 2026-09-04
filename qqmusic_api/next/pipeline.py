"""CGI 请求管道. 串联上下文参数构建、传输发送与端点解析, 并发出观测事件."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from niquests.exceptions import RequestException

from ..core.exceptions import ApiDataError, CredentialInvalidError, GlobalApiError, HTTPError, NetworkError
from ..core.versioning import Platform
from ..models.request import Credential
from ..utils.common import bool_to_int
from .endpoint import CgiEndpoint
from .transport import RawResponse, Transport


class CgiContext(Protocol):
    """管道所需的 CGI 上下文窄接口 (ApiContext 的结构化子集)."""

    credential: Credential

    async def build_api_kwargs(
        self,
        data: Sequence[dict[str, Any]],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        *,
        override_comm: bool = False,
        sign: bool = False,
    ) -> tuple[str, dict[str, Any], dict[str, str], dict[str, str]]:
        """构建 CGI 调用的 URL、payload、params 与 headers 四元组."""
        ...


@dataclass(frozen=True)
class RequestEvent:
    """单次管道执行的观测事件.

    Attributes:
        endpoint: 端点标识, 形如 "module/method".
        elapsed: 执行耗时 (秒).
        error: 执行期间抛出的异常, 成功时为 None.
        path: 流量路径标记, 新内核固定为 "v2".
    """

    endpoint: str
    elapsed: float
    error: BaseException | None
    path: str = "v2"


class Pipeline:
    """CGI 请求执行管道 (单请求路径, 批量合并留待后续计划)."""

    def __init__(
        self,
        context: CgiContext,
        transport: Transport,
        *,
        on_event: Callable[[RequestEvent], None] | None = None,
    ) -> None:
        """初始化管道.

        Args:
            context: CGI 上下文窄接口 (生产环境传入 ApiContext).
            transport: 传输实现.
            on_event: 可选的观测事件回调.
        """
        self._context = context
        self._transport = transport
        self._on_event = on_event

    async def execute(
        self,
        endpoint: CgiEndpoint,
        param: dict[str, Any],
        *,
        credential: Credential | None = None,
        comm: dict[str, Any] | None = None,
        override_comm: bool = False,
    ) -> Any:
        """执行单条 CGI 端点调用并返回解析结果.

        Args:
            endpoint: 端点声明.
            param: 请求参数字典.
            credential: 可选的凭证对象, 优先于上下文默认凭证.
            comm: 可选的公共参数.
            override_comm: 是否完全覆盖默认公共参数.

        Returns:
            端点声明的解析结果.

        Raises:
            CredentialInvalidError: 端点要求登录但缺少有效凭证.
            NetworkError: 网络传输异常.
            HTTPError: HTTP 状态码异常.
            ApiDataError: 响应载荷解析失败或缺少子响应.
            GlobalApiError: 外层信封被网关拒绝.
            CgiApiException: 业务错误码经注册表映射后抛出.
        """
        if endpoint.require_login:
            cred = credential or self._context.credential
            if not cred or not cred.musicid or not cred.musickey:
                raise CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")

        url, payload, params, headers = await self._context.build_api_kwargs(
            data=[
                {
                    "module": endpoint.module,
                    "method": endpoint.method,
                    "param": param if endpoint.preserve_bool else bool_to_int(param),
                }
            ],
            comm=comm,
            credential=credential,
            platform=endpoint.platform,
            override_comm=override_comm,
            sign=endpoint.sign,
        )

        start = time.monotonic()
        error: BaseException | None = None
        try:
            resp = await self._transport.post(url, json=payload, params=params, headers=headers)
            raw_data = self._unwrap_cgi_batch(resp, expected_count=1)[0]
            return endpoint.parse_data(raw_data)
        except RequestException as exc:
            error = NetworkError(str(exc))
            raise error from exc
        except BaseException as exc:
            error = exc
            raise
        finally:
            if self._on_event is not None:
                self._on_event(
                    RequestEvent(
                        endpoint=f"{endpoint.module}/{endpoint.method}",
                        elapsed=time.monotonic() - start,
                        error=error,
                    )
                )

    @staticmethod
    def _unwrap_cgi_batch(response: RawResponse, expected_count: int) -> list[dict[str, Any]]:
        """拆解并校验 CGI 批量响应的外层信封, 语义与旧 Client._unwrap_cgi_batch 一致."""
        if response.status_code != 200:
            raise HTTPError(
                f"HTTP 请求状态码异常: {response.status_code}",
                status_code=cast("int", response.status_code),
            )
        if not response.content:
            raise ApiDataError("响应无内容")
        try:
            resp = response.json()
        except Exception as exc:
            raise ApiDataError("响应内容非有效 JSON 格式") from exc
        code: int = cast("dict", resp).pop("code", 0)

        if code != 0:
            raise GlobalApiError("Module 请求失败", code=code, data=response.text)

        try:
            return [resp[f"req_{i}"] for i in range(expected_count)]
        except KeyError as exc:
            raise ApiDataError(f"CGI 响应格式异常, 缺少预期的子响应: {exc}") from exc
