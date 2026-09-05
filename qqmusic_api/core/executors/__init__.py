"""请求执行器包."""

from .cgi import CgiExecutor
from .http import HttpExecutor

__all__ = [
    "CgiExecutor",
    "HttpExecutor",
]
