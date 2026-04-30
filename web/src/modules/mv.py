"""MV 模块 Web 路由适配."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from qqmusic_api import Client
from web.src.deps import client_dependency
from web.src.response import ApiResponse

router = APIRouter(prefix="/mv", tags=["mv"])


@router.get(
    "/get_mv_urls",
    summary="批量获取 MV 播放链接",
    description="批量获取 MV 播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_urls_get(
    vids: Annotated[list[str], Query(description="视频 VID 列表.")],
    client: Client = client_dependency,
):
    """批量获取 MV 播放链接."""
    return await client.mv.get_mv_urls(vids)


@router.get(
    "/{vid}/url",
    summary="获取单个 MV 播放链接",
    description="根据单个 MV VID 获取播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_url_get(
    vid: Annotated[str, Path(description="MV VID.")],
    client: Client = client_dependency,
):
    """根据单个 MV VID 获取播放链接."""
    return await client.mv.get_mv_urls([vid])
