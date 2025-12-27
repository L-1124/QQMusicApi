"""请求 Session 管理"""

import contextvars
import logging
from typing import TypedDict

import httpx

from .credential import Credential
from .qimei import get_qimei

# 配置日志记录器
logger = logging.getLogger(__name__)


class ApiConfig(TypedDict):
    """API 配置"""

    version: str
    version_code: int
    enable_sign: bool
    endpoint: str
    enc_endpoint: str


class Session(httpx.AsyncClient):
    """Session 类,用于管理 QQ 音乐的登录态和 API 请求

    Args:
        credential: 全局凭证,每个请求都将使用.
        enable_sign: 是否启用加密接口
    """

    HOST = "y.qq.com"
    UA_DEFAULT = "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54"

    def __init__(
        self,
        *,
        credential: Credential | None = None,
        enable_sign: bool = False,
        http2: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs, http2=http2)
        self.credential = credential
        self.headers.update(
            {
                "User-Agent": self.UA_DEFAULT,
                "Referer": self.HOST,
            }
        )
        self.api_config = ApiConfig(
            version="13.2.5.8",
            version_code=13020508,
            enable_sign=enable_sign,
            endpoint="https://u.y.qq.com/cgi-bin/musicu.fcg",
            enc_endpoint="https://u.y.qq.com/cgi-bin/musics.fcg",
        )
        self.qimei = get_qimei(self.api_config["version"])["q36"]

    async def __aenter__(self) -> "Session":
        """进入 async with 上下文时调用"""
        self._previous_session = _session_context.set(self)
        return self

    async def __aexit__(self, *args, **kwargs) -> None:
        """退出 async with 上下文时调用"""
        _session_context.reset(self._previous_session)
        await self.aclose()


_session_context: contextvars.ContextVar[Session | None] = contextvars.ContextVar("_session_context", default=None)


def get_session() -> Session:
    """获取当前上下文的 Session"""
    session = _session_context.get()
    if session is None:
        logger.info("创建新的默认Session")
        session = Session()
        _session_context.set(session)
    return session


def set_session(session: Session) -> None:
    """设置当前上下文的 Session"""
    logger.info("设置新的Session到上下文")
    _session_context.set(session)


def clear_session() -> None:
    """清除当前上下文的 Session"""
    logger.info("清除当前上下文的Session")
    try:
        _session_context.set(None)
    except LookupError:
        logger.warning("尝试清除不存在的Session上下文")
        pass
