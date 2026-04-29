"""MV 模块 Web 路由适配."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Path, Query, Request

from web.response import ApiResponse, success_response

if TYPE_CHECKING:
    from qqmusic_api import Client

router = APIRouter(prefix="/mv", tags=["mv"])


@router.get(
    "/get_mv_urls",
    summary="批量获取 MV 播放链接",
    description="批量获取 MV 播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_urls_get(
    request: Request,
    vids: Annotated[list[str], Query(description="视频 VID 列表.")],
):
    """批量获取 MV 播放链接."""
    client: Client = request.app.state.client
    return success_response(await client.mv.get_mv_urls(vids))


@router.get(
    "/{vid}/url",
    summary="获取单个 MV 播放链接",
    description="根据单个 MV VID 获取播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_url_get(
    request: Request,
    vid: Annotated[str, Path(description="MV VID.")],
):
    """根据单个 MV VID 获取播放链接."""
    client: Client = request.app.state.client
    return success_response(await client.mv.get_mv_urls([vid]))
