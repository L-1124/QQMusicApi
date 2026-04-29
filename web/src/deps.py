"""Web 层依赖注入."""

from fastapi import Depends, Request

from qqmusic_api import Client


def get_client(request: Request) -> Client:
    """获取当前请求绑定的 Client 实例."""
    return request.app.state.client


client_dependency = Depends(get_client)
