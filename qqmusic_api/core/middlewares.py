"""请求中间件机制"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .client import Client
    from .request import Request


class RequestMiddleware(Protocol):
    """请求中间件接口"""

    async def process_request(self, request: "Request", client: "Client") -> "Request":
        """处理请求并返回加工后的 Request 对象。"""
        ...


class CommContextMiddleware:
    """公共上下文装配中间件。

    自动合并全局设备、凭据配置与局部请求中的 comm 参数，并提取最新的 QIMEI。
    """

    async def process_request(self, request: "Request", client: "Client") -> "Request":
        """执行装配流程。"""
        target_platform = request.platform or client.platform
        target_credential = request.credential or client.credential

        base_comm = await client._build_common_params(target_platform, target_credential)

        if request.comm:
            base_comm.update(request.comm)

        request.comm = base_comm
        return request


class SignDecisionMiddleware:
    """签名决策中间件。

    提前判断该请求是否需要接受 payload 签名并预置指示信号。
    """

    async def process_request(self, request: "Request", client: "Client") -> "Request":
        """评估签名许可并预留指示。"""
        # 针对支持且需要的场景下发放签名授权标志
        if client.enable_sign and not request.is_jce:
            request.http_params_extra["_internal_need_sign"] = "1"
        return request
