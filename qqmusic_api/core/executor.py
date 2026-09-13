"""请求执行器. CGI 与 HTTP 两类执行单元, 以及各自的参数准备.

每个 CGI 批次都是独立执行单元: 准备 → 单物理请求 → 信封解包 →
逐项解析 → 释放响应. 每个 HTTP 请求独立执行: 准备 → 单物理请求 →
解析 → 释放. 批量发送统一经 ``transport.send_many`` 适配; 批次解析
与响应交付各只有一份实现.

执行器独占登录校验, 规范分组键与批次切块; 身份一律取自执行条目
的 scope, 不回读原请求或 Client 默认值. 准备阶段复制需要修改的
字典, 不修改调用者传入的原始数据.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import anyio
import orjson as json

from ..algorithms import zzc_sign
from ..utils.android_session import AndroidSessionManager
from ..utils.common import bool_to_int
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .engine import OperationScope, RequestScope, ScopedCall, credential_fingerprint
from .exceptions import ApiDataError, CredentialInvalidError, NetworkError
from .request import CgiRequest, HttpRequest
from .response import parse_cgi_item, parse_http_response, unwrap_cgi_envelope
from .transport import (
    DEFAULT_MAX_CONCURRENCY,
    PreparedRequest,
    Transport,
    TransportError,
    send_many,
)
from .versioning import Platform, VersionPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..models.request import Credential

MUSICU_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
MUSICS_URL = "https://u.y.qq.com/cgi-bin/musics.fcg"


def _has_valid_credential(credential: "Credential") -> bool:
    """判断凭证是否具备登录要素.

    Args:
        credential: 待检查的凭证.

    Returns:
        凭证是否有效.
    """
    return bool(credential.musicid and credential.musickey)


def _to_network_error(exc: TransportError) -> NetworkError:
    """将内部传输异常转换为公开网络异常.

    Args:
        exc: 传输边界抛出的异常.

    Returns:
        公开 NetworkError 实例.
    """
    return NetworkError(str(exc))


async def _release_response(transport: Transport, response: Any) -> None:
    """屏蔽取消并释放一个已接收的响应."""
    with anyio.CancelScope(shield=True):
        await transport.release(response)


@dataclass(frozen=True)
class CgiBatchKey:
    """CGI 批量合并的分组键.

    仅包含影响线上公共参数的字段: 快照平台, 完整凭证指纹, 规范化的
    comm (None 与空 dict 一致), override_comm 与 sign. ``preserve_bool``
    ``require_login`` 与解析选项不进入键.
    """

    platform: Platform
    fingerprint: str
    comm: str | None
    override_comm: bool
    sign: bool

    @classmethod
    def from_call(cls, call: ScopedCall) -> "CgiBatchKey":
        """从执行条目计算分组键.

        Args:
            call: 执行条目 (身份取自 scope).

        Returns:
            可比较的分组键实例.
        """
        canonical_comm = _canonical_json(call.request.comm) if call.request.comm else None
        return cls(
            platform=call.scope.platform,
            fingerprint=credential_fingerprint(call.scope.credential),
            comm=canonical_comm,
            override_comm=call.request.override_comm,
            sign=call.request.sign,
        )


def _canonical_json(value: Any) -> str:
    """按键序规范化序列化为 JSON 字符串.

    Args:
        value: 待序列化的值.

    Returns:
        规范化 JSON 字符串.
    """
    return json.dumps(value, option=json.OPT_SORT_KEYS).decode()


@dataclass(frozen=True)
class CgiBatch:
    """同组 CGI 请求批次 (由 CgiExecutor 独占构造).

    Attributes:
        scope: 批次共享的运行时快照.
        calls: 批次内的执行条目 (线上环境已保证一致).
    """

    scope: RequestScope
    calls: tuple[ScopedCall, ...]


class CgiExecutor:
    """CGI 请求执行器. 独占登录校验, 参数准备, 规范分组键与批次切块."""

    def __init__(
        self,
        *,
        android_session: AndroidSessionManager,
        device_store: DeviceManager,
        qimei_manager: QimeiManager,
        version_policy: VersionPolicy,
        transport: Transport,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """初始化 CGI 执行器.

        Args:
            android_session: Android 会话管理器.
            device_store: 设备信息管理器.
            qimei_manager: QIMEI 管理器.
            version_policy: 版本策略规则.
            transport: 单物理请求传输边界.
            max_concurrency: 批量发送的容量上限.
        """
        self._android_session = android_session
        self._device_store = device_store
        self._qimei_manager = qimei_manager
        self._version_policy = version_policy
        self._transport = transport
        self._max_concurrency = max_concurrency

    async def execute_one(self, call: ScopedCall) -> Any:
        """执行单个 CGI 请求条目并返回解析结果.

        异常直接抛出, 不包装为异常组; 准备阶段 (QIMEI/Android Session)
        与传输阶段的网络异常统一转换为 ``NetworkError``.

        Args:
            call: 执行条目 (身份取自 scope).

        Returns:
            解析后的结果对象.

        Raises:
            CredentialInvalidError: 请求需要登录但凭证无效.
            NetworkError: 网络传输异常 (含准备阶段的 QIMEI/Android Session 请求).
        """
        request = self._cast_request(call)
        if request.require_login and not _has_valid_credential(call.scope.credential):
            raise CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")

        batch = CgiBatch(scope=call.scope, calls=(call,))
        prepared = await self._prepare_batch(batch)
        outcome = (
            await send_many(
                self._transport,
                [prepared],
                max_concurrency=self._max_concurrency,
            )
        )[0]
        if isinstance(outcome, Exception):
            if isinstance(outcome, TransportError):
                raise _to_network_error(outcome) from outcome
            raise outcome

        try:
            result = self._decode_batch(batch, outcome)[0]
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            await _release_response(self._transport, outcome)

    async def execute_many(
        self,
        calls: "Sequence[ScopedCall]",
        *,
        batch_size: int,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """执行索引化的 CGI 请求条目集合.

        逐项执行 ``require_login`` 校验后按快照身份分组并按 ``batch_size``
        切块; 全部批次一次性经 ``send_many`` 批量发送, 批次级网络错误
        映射到该信封内的全部子项, 单个子项的解析错误只影响对应位置.
        分组阶段的普通异常同样按上述作用范围回填, 取消类
        ``BaseException`` 始终直接传播.

        Args:
            calls: 执行条目序列.
            batch_size: 单个批次包含的最大请求数.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表.

        Raises:
            CredentialInvalidError: ``return_exceptions`` 为 False 且存在
                登录校验失败的请求.
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        results: dict[int, Any] = {}
        groups: defaultdict[CgiBatchKey, list[ScopedCall]] = defaultdict(list)
        for call in calls:
            request = self._cast_request(call)
            try:
                key = CgiBatchKey.from_call(call)
            except Exception as exc:
                if return_exceptions:
                    results[call.index] = exc
                    continue
                raise
            if request.require_login and not _has_valid_credential(call.scope.credential):
                exc = CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")
                if return_exceptions:
                    results[call.index] = exc
                    continue
                raise exc
            groups[key].append(call)

        if not groups:
            return list(results.items())

        batches: list[CgiBatch] = []
        for group in groups.values():
            for start in range(0, len(group), batch_size):
                chunk = group[start : start + batch_size]
                batches.append(CgiBatch(scope=chunk[0].scope, calls=tuple(chunk)))

        prepared: list[tuple[CgiBatch, PreparedRequest]] = []
        for batch in batches:
            try:
                prepared.append((batch, await self._prepare_batch(batch)))
            except TransportError as exc:  # noqa: PERF203
                error = _to_network_error(exc)
                if not return_exceptions:
                    raise error from exc
                for call in batch.calls:
                    results[call.index] = error
            except Exception as exc:
                if not return_exceptions:
                    raise
                for call in batch.calls:
                    results[call.index] = exc

        if prepared:
            outcomes = await send_many(
                self._transport,
                [item for _, item in prepared],
                max_concurrency=self._max_concurrency,
            )
            first_error: Exception | None = None
            for (batch, _), outcome in zip(prepared, outcomes, strict=True):
                if isinstance(outcome, Exception):
                    error = _to_network_error(outcome) if isinstance(outcome, TransportError) else outcome
                    if return_exceptions:
                        for call in batch.calls:
                            results[call.index] = error
                    elif first_error is None:
                        first_error = error
                    continue
                try:
                    decoded = self._decode_batch(batch, outcome)
                    for position, call in enumerate(batch.calls):
                        item_outcome = decoded[position]
                        if isinstance(item_outcome, Exception):
                            if return_exceptions:
                                results[call.index] = item_outcome
                            elif first_error is None:
                                first_error = item_outcome
                        else:
                            results[call.index] = item_outcome
                finally:
                    await _release_response(self._transport, outcome)
            if first_error is not None:
                raise first_error

        return list(results.items())

    @staticmethod
    def _cast_request(call: ScopedCall) -> CgiRequest[Any]:
        """取回执行条目中的 CGI 请求副本.

        Args:
            call: 执行条目.

        Returns:
            CGI 请求描述符.
        """
        request = call.request
        assert isinstance(request, CgiRequest)
        return request

    def _decode_batch(self, batch: CgiBatch, response: Any) -> "list[Any]":
        """解析整个批次: 信封解包与逐项解析的唯一实现.

        单个子项错误只影响对应位置, 兄弟项继续解析.

        Args:
            batch: 请求批次.
            response: 本批次的原始响应.

        Returns:
            逐项结果列表, 元素为解析结果或异常.
        """
        try:
            items = unwrap_cgi_envelope(response, expected_count=len(batch.calls))
        except Exception as exc:
            return [exc] * len(batch.calls)
        out: list[Any] = []
        for position, call in enumerate(batch.calls):
            item = items[position]
            if item is None:
                out.append(ApiDataError(f"CGI 响应格式异常, 缺少或畸形子响应 req_{position}"))
                continue
            try:
                out.append(self._parse_item(item, self._cast_request(call)))
            except Exception as exc:
                out.append(exc)
        return out

    def _parse_item(self, raw: dict[str, Any], request: CgiRequest[Any]) -> Any:
        """按请求描述符的解析选项解析单个子响应.

        Args:
            raw: CGI 子响应字典.
            request: 请求描述符.

        Returns:
            解析后的结果对象.
        """
        return parse_cgi_item(
            raw,
            allow_error_codes=request.allow_error_codes,
            parse_on_allow=request.parse_on_allow,
            disable_parse=request.disable_parse,
            response_model=request.response_model,
        )

    async def _prepare_batch(self, batch: CgiBatch) -> PreparedRequest:
        """组装批次传输请求 (原 CgiPreparer 逻辑).

        ANDROID 平台先确保会话并获取 QIMEI; 用户 comm 覆盖优先,
        ``override_comm`` 表示完全替换; 签名批次切换 URL 并附加时间戳.

        Args:
            batch: 请求批次.

        Returns:
            准备完成的传输请求.

        Raises:
            NetworkError: 准备阶段的 QIMEI/Android Session 请求失败.
        """
        if not batch.calls:
            raise ValueError("CGI 批次不能为空")

        scope = batch.scope
        base = self._cast_request(batch.calls[0])

        session = None
        try:
            if scope.platform == Platform.ANDROID:
                session = await self._android_session.ensure(scope.credential)

            device = await self._device_store.get_device()
            qimei = await self._qimei_manager.get_cached() if scope.platform == Platform.ANDROID else None
        except TransportError as exc:
            raise _to_network_error(exc) from exc
        final_comm = self._build_comm(base, scope, device, qimei, session)
        user_agent = self._version_policy.get_user_agent(scope.platform, device)

        payload: dict[str, Any] = {"comm": final_comm}
        for idx, call in enumerate(batch.calls):
            request = self._cast_request(call)
            payload[f"req_{idx}"] = {
                "module": request.module,
                "method": request.method,
                "param": request.param if request.preserve_bool else bool_to_int(request.param),
            }

        params: dict[str, str] = {}
        if base.sign:
            import time

            params["_"] = str(int(time.time() * 1000))
            params["sign"] = zzc_sign(json.dumps(payload))

        url = MUSICS_URL if base.sign else MUSICU_URL
        return PreparedRequest(
            method="POST",
            url=url,
            kwargs={"json": payload, "params": params, "headers": {"User-Agent": user_agent}},
        )

    def _build_comm(
        self,
        base: CgiRequest[Any],
        scope: RequestScope,
        device: Any,
        qimei: Any,
        session: Any = None,
    ) -> dict[str, Any]:
        """构建批次公共参数 (不修改用户传入的 comm 字典).

        Args:
            base: 批次内首个请求.
            scope: 批次共享的运行时快照.
            device: 当前设备对象.
            qimei: QIMEI 缓存, 仅 ANDROID 平台非空.
            session: Android 会话值, 仅 ANDROID 平台非空.

        Returns:
            合并或覆盖后的 comm 字典.
        """
        if base.override_comm:
            return dict(base.comm or {})

        final = self._version_policy.build_comm(
            platform=scope.platform,
            credential=scope.credential,
            device=device,
            qimei=qimei,
            guid=device.open_udid,
            session=session,
        )
        if base.comm:
            final.update(base.comm)
        return final


class HttpExecutor:
    """HTTP 请求执行器. 请求不合并, 经共享批量辅助并发执行."""

    def __init__(
        self,
        *,
        device_store: DeviceManager,
        version_policy: VersionPolicy,
        transport: Transport,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """初始化 HTTP 执行器.

        Args:
            device_store: 设备信息管理器.
            version_policy: 版本策略规则.
            transport: 单物理请求传输边界.
            max_concurrency: 批量发送的容量上限.
        """
        self._device_store = device_store
        self._version_policy = version_policy
        self._transport = transport
        self._max_concurrency = max_concurrency

    async def execute_one(
        self,
        call: ScopedCall,
        *,
        operation: OperationScope | None = None,
    ) -> Any:
        """执行单个 HTTP 请求条目并返回解析结果.

        Args:
            call: 执行条目 (身份取自 scope).
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.

        Returns:
            解析后的结果对象; disable_parse 时为原始响应 (已登记,
            由 Engine 在操作成功返回时移交所有权).

        Raises:
            NetworkError: 网络传输异常.
        """
        operation = operation or OperationScope(self._transport)
        prepared = await self._prepare(call)
        outcome = (
            await send_many(
                self._transport,
                [prepared],
                max_concurrency=self._max_concurrency,
            )
        )[0]
        if isinstance(outcome, Exception):
            if isinstance(outcome, TransportError):
                raise _to_network_error(outcome) from outcome
            raise outcome
        return await self._deliver(call, outcome, operation)

    async def execute_many(
        self,
        calls: "Sequence[ScopedCall]",
        *,
        operation: OperationScope | None = None,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """并发执行索引化的 HTTP 请求条目集合.

        全部条目一次性经 ``send_many`` 批量发送, 每项错误只影响对应
        位置; 取消类 ``BaseException`` 始终直接传播.

        Args:
            calls: 执行条目序列.
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表.

        Raises:
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        operation = operation or OperationScope(self._transport)
        results: dict[int, Any] = {}
        prepared_calls: list[tuple[ScopedCall, PreparedRequest]] = []
        for call in calls:
            try:
                prepared_calls.append((call, await self._prepare(call)))
            except Exception as exc:  # noqa: PERF203
                if return_exceptions:
                    results[call.index] = exc
                else:
                    raise

        if prepared_calls:
            outcomes = await send_many(
                self._transport,
                [item for _, item in prepared_calls],
                max_concurrency=self._max_concurrency,
            )
            first_error: Exception | None = None
            for (call, _), outcome in zip(prepared_calls, outcomes, strict=True):
                try:
                    if isinstance(outcome, Exception):
                        if isinstance(outcome, TransportError):
                            raise _to_network_error(outcome) from outcome
                        raise outcome
                    results[call.index] = await self._deliver(call, outcome, operation)
                except Exception as exc:  # noqa: PERF203
                    if return_exceptions:
                        results[call.index] = exc
                    elif first_error is None:
                        first_error = exc
            if first_error is not None:
                raise first_error

        return list(results.items())

    async def _prepare(self, call: ScopedCall) -> PreparedRequest:
        """组装 HTTP 传输请求 (原 HttpPreparer 逻辑).

        注入 scope 凭证 Cookie, 用户 Cookie 优先; 按不区分大小写的
        header 名检查 UA, 缺失时注入 WEB 平台 UA; 全部 HTTP options
        原样透传; 复制需要修改的字典, 不修改调用者传入的原始数据.

        Args:
            call: 执行条目.

        Returns:
            准备完成的传输请求.
        """
        request: HttpRequest[Any] = call.request
        scope = call.scope

        kwargs: dict[str, Any] = {}
        if request.params is not None:
            kwargs["params"] = request.params
        if request.headers is not None:
            kwargs["headers"] = dict(request.headers)
        if request.json is not None:
            kwargs["json"] = request.json
        if request.data is not None:
            kwargs["data"] = request.data
        if request.kwargs is not None:
            kwargs.update(request.kwargs)

        cookies: dict[str, str] = {}
        credential = scope.credential
        if credential.musicid:
            uin = credential.str_musicid or str(credential.musicid)
            cookies["uin"] = uin
            cookies["qqmusic_uin"] = uin
        if credential.musickey:
            cookies["qm_keyst"] = credential.musickey
            cookies["qqmusic_key"] = credential.musickey
        if request.cookies:
            cookies.update(cast("dict[str, str]", request.cookies))
        if cookies:
            kwargs["cookies"] = cookies

        headers: dict[str, Any] = kwargs.get("headers") or {}
        if not any(name.lower() == "user-agent" for name in headers):
            device = await self._device_store.get_device()
            headers["User-Agent"] = self._version_policy.get_user_agent(Platform.WEB, device)
            kwargs["headers"] = headers

        return PreparedRequest(method=request.method, url=request.url, kwargs=kwargs)

    async def _deliver(self, call: ScopedCall, response: Any, operation: OperationScope) -> Any:
        """交付响应: 原始响应登记移交, 其余解析后立即释放.

        Args:
            call: 执行条目.
            response: 原始响应.
            operation: 本次操作的资源登记表.

        Returns:
            解析后的结果对象或原始响应.

        Raises:
            Exception: 解析失败 (响应已释放).
        """
        delivered = False
        try:
            if call.request.disable_parse:
                operation.track(response)
                delivered = True
                return response
            return self._decode(response, call)
        finally:
            if not delivered:
                await _release_response(self._transport, response)

    def _decode(self, response: Any, call: ScopedCall) -> Any:
        """按请求描述符的解析选项解析 HTTP 响应.

        Args:
            response: 原始响应.
            call: 执行条目.

        Returns:
            解析后的结果对象.
        """
        return parse_http_response(
            response,
            disable_parse=call.request.disable_parse,
            response_model=call.request.response_model,
        )
