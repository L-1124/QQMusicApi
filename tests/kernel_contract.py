"""内核行为契约共享桩基础设施.

供 Client/执行器/传输层等 Core 测试复用的桩与载荷构造器.
桩只模拟外部边界 (会话/传输/响应), 不 Mock 被测对象自身的内部方法.

严格 code 契约: CGI 外层与子响应 code 使用 ``type(code) is int`` 严格校验,
浮点 (``2000.0``/``0.0``)、布尔 (``False``) 与字符串码一律抛出 ``ApiDataError``,
对应的参数化断言见 ``tests/test_response.py``.
"""

from typing import Any

import niquests

__all__ = [
    "StubResponse",
    "StubSession",
    "StubTransport",
    "make_cgi_envelope",
    "make_cgi_sub",
]


class StubResponse:
    """可配置 status/content/text/json/error 的响应桩."""

    def __init__(
        self,
        payload: Any,
        status_code: int = 200,
        *,
        content: bytes | None = b"{}",
        text: str | None = "",
        json_error: bool = False,
        http_error: bool = False,
    ) -> None:
        """以预置载荷与可选状态码构造响应桩.

        Args:
            payload: 供 json() 返回的载荷.
            status_code: HTTP 状态码.
            content: 原始响应体, 用于触发 "响应无内容" 分支.
            text: 响应文本.
            json_error: 是否让 json() 抛出解析异常.
            http_error: 是否让 raise_for_status() 抛出 HTTP 状态异常.
        """
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.text = text
        self._json_error = json_error
        self._http_error = http_error

    def json(self) -> Any:
        """按预置标记返回载荷或抛出解析异常."""
        if self._json_error:
            raise ValueError("模拟 JSON 解析失败")
        return self._payload

    def raise_for_status(self) -> None:
        """按预置标记抛出 HTTP 状态异常."""
        if self._http_error:
            raise niquests.HTTPError(f"HTTP {self.status_code}")


class StubSession:
    """记录 post/request 调用并按队列返回预置响应的旧会话桩."""

    def __init__(self, posts: list[Any] | None = None, requests: list[Any] | None = None) -> None:
        """以预置的 CGI 与 HTTP 响应/异常队列构造会话桩."""
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.request_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.gather_calls: list[tuple[Any, ...]] = []
        self.close_calls = 0
        self._posts = list(posts or [])
        self._requests = list(requests or [])

    async def post(self, url: str, **kwargs: Any) -> StubResponse:
        """记录 CGI 调用并返回或抛出下一个预置项."""
        self.post_calls.append((url, kwargs))
        if not self._posts:
            raise AssertionError(f"CGI 会话桩队列耗尽, 意外网络调用: {url}")
        item = self._posts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def request(self, method: str, url: str, **kwargs: Any) -> StubResponse:
        """记录 HTTP 调用并返回或抛出下一个预置项."""
        self.request_calls.append((method, url, kwargs))
        if not self._requests:
            raise AssertionError(f"HTTP 会话桩队列耗尽, 意外网络调用: {method} {url}")
        item = self._requests.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def gather(self, *responses: Any) -> None:
        """记录收集调用, 测试桩中不做额外处理."""
        self.gather_calls.append(responses)

    async def close(self) -> None:
        """记录关闭调用."""
        self.close_calls += 1


class StubTransport:
    """记录 request/release/close 调用并按队列返回预置结果的传输桩."""

    def __init__(self, starts: list[Any] | None = None) -> None:
        """以预置的 request 结果/异常队列构造传输桩.

        Args:
            starts: request() 按序返回的响应列表, 元素为异常时抛出;
                队列耗尽时抛出 AssertionError. 可在运行前继续追加.
        """
        self.start_calls: list[Any] = []
        self.release_calls: list[Any] = []
        self.close_calls = 0
        self._closed = False
        self.starts = list(starts or [])

    async def request(self, request: Any) -> Any:
        """记录 request 调用并返回或抛出下一个预置项."""
        self.start_calls.append(request)
        if not self.starts:
            raise AssertionError(f"传输桩队列耗尽, 意外网络调用: {request.method} {request.url}")
        item = self.starts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def release(self, response: Any) -> None:
        """记录释放调用."""
        self.release_calls.append(response)

    async def close(self) -> None:
        """记录关闭调用, 幂等."""
        if self._closed:
            return
        self._closed = True
        self.close_calls += 1


def make_cgi_sub(code: int | Any = 0, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造单个 CGI 子响应字典.

    Args:
        code: 子响应业务码.
        data: 子响应 data 字段.
    """
    return {"code": code, "data": data or {}}


def make_cgi_envelope(sub_payloads: list[dict[str, Any]]) -> StubResponse:
    """构造包含多个子响应的 CGI 批量响应桩.

    Args:
        sub_payloads: 按序写入 req_0, req_1, ... 的子响应列表.
    """
    payload: dict[str, Any] = {"code": 0}
    for idx, sub in enumerate(sub_payloads):
        payload[f"req_{idx}"] = sub
    return StubResponse(payload)
