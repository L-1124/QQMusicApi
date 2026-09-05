"""CGI 单次与批量执行器."""

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ..exceptions import CredentialInvalidError, NetworkError
from ..preparation import CgiBatchKey, CgiPreparer
from ..request import CgiRequest, CgiRequestResultT
from ..response import parse_cgi_item, unwrap_cgi_envelope
from ..runtime import ClientDefaults, RequestScope, resolve_scope
from ..transport import Transport, TransportError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...models.request import Credential
    from ..transport import RawResponse


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


class CgiExecutor:
    """CGI 请求执行器. 串联准备器, 传输与响应解析."""

    def __init__(
        self,
        *,
        defaults: ClientDefaults,
        preparer: CgiPreparer,
        transport: Transport,
    ) -> None:
        """初始化 CGI 执行器.

        Args:
            defaults: 客户端级默认运行时状态.
            preparer: CGI 批次准备器.
            transport: 两阶段传输边界.
        """
        self._defaults = defaults
        self._preparer = preparer
        self._transport = transport

    async def execute_one(self, request: CgiRequest[CgiRequestResultT]) -> CgiRequestResultT:
        """执行单个 CGI 请求并返回解析结果.

        异常直接抛出, 不包装为异常组; 准备阶段 (QIMEI/Android Session)
        与传输阶段的网络异常统一转换为 ``NetworkError``.

        Args:
            request: CGI 请求描述符.

        Returns:
            解析后的结果对象.

        Raises:
            CredentialInvalidError: 请求需要登录但凭证无效.
            NetworkError: 网络传输异常 (含准备阶段的 QIMEI/Android Session 请求).
        """
        scope = resolve_scope(request, self._defaults)
        if request.require_login and not _has_valid_credential(scope.credential):
            raise CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")

        try:
            prepared = await self._preparer.prepare_batch([request], scope)
            response = await self._transport.start(prepared)
            await self._transport.resolve([response])
        except TransportError as exc:
            raise _to_network_error(exc) from exc

        items = unwrap_cgi_envelope(response, expected_count=1)
        return self._parse_item(items[0], request)

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

    async def execute_many(
        self,
        requests: "Sequence[tuple[int, CgiRequest[Any]]]",
        *,
        batch_size: int,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """执行索引化的 CGI 请求集合.

        按 ``CgiBatchKey`` 分组并按 ``batch_size`` 切块, 各批次先后发起,
        最后通过单次 ``resolve`` 集中等待; 批次级网络或信封错误影响该批次
        全部位置, 单个子项的解析错误只影响对应位置. 分组键计算与准备阶段
        的普通异常同样按上述作用范围回填, 取消类 ``BaseException`` 始终
        直接传播.

        Args:
            requests: (原始索引, 请求描述符) 序列.
            batch_size: 单个批次包含的最大请求数.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表, 按原始索引升序排列.

        Raises:
            CredentialInvalidError: ``return_exceptions`` 为 False 且存在
                登录校验失败的请求.
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        results: dict[int, Any] = {}
        request_by_index = dict(requests)
        scopes: dict[int, RequestScope] = {}
        groups: defaultdict[CgiBatchKey, list[tuple[int, CgiRequest[Any]]]] = defaultdict(list)
        for index, request in requests:
            try:
                scope = resolve_scope(request, self._defaults)
                key = CgiBatchKey.from_request(request, scope)
            except Exception as exc:
                if return_exceptions:
                    results[index] = exc
                    continue
                raise
            scopes[index] = scope
            if request.require_login and not _has_valid_credential(scope.credential):
                exc = CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")
                if return_exceptions:
                    results[index] = exc
                    continue
                raise exc
            groups[key].append((index, request))

        if not groups:
            return sorted(results.items())

        batches: list[list[int]] = []
        for group in groups.values():
            for start in range(0, len(group), batch_size):
                chunk = group[start : start + batch_size]
                batches.append([index for index, _ in chunk])

        in_flight: list[tuple[list[int], RawResponse]] = []
        for indices in batches:
            chunk = [request_by_index[index] for index in indices]
            try:
                prepared = await self._preparer.prepare_batch(chunk, scopes[indices[0]])
                response = await self._transport.start(prepared)
            except TransportError as exc:
                if return_exceptions:
                    error = _to_network_error(exc)
                    for index in indices:
                        results[index] = error
                    continue
                raise _to_network_error(exc) from exc
            except Exception as exc:
                if return_exceptions:
                    for index in indices:
                        results[index] = exc
                    continue
                raise
            in_flight.append((indices, response))

        try:
            await self._transport.resolve([response for _, response in in_flight])
        except TransportError as exc:
            if not return_exceptions:
                raise _to_network_error(exc) from exc
            error = _to_network_error(exc)
            for indices, _ in in_flight:
                for index in indices:
                    results[index] = error
            return sorted(results.items())

        for indices, response in in_flight:
            try:
                items = unwrap_cgi_envelope(response, expected_count=len(indices))
            except Exception as exc:
                if return_exceptions:
                    for index in indices:
                        results[index] = exc
                    continue
                raise
            for position, index in enumerate(indices):
                try:
                    results[index] = self._parse_item(items[position], request_by_index[index])
                except Exception as exc:  # noqa: PERF203
                    if return_exceptions:
                        results[index] = exc
                    else:
                        raise

        return sorted(results.items())
