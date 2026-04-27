"""MV 模块 Web 路由适配."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from qqmusic_api.models.mv import GetMvUrlsResponse
from web.response import ApiResponse, success_response

if TYPE_CHECKING:
    from qqmusic_api import Client

router = APIRouter(prefix="/mv", tags=["mv"])

OPENAPI_RESPONSE_MODELS = {
    ("/mv/get_mv_urls", "get"): GetMvUrlsResponse,
    ("/mv/get_mv_urls", "post"): GetMvUrlsResponse,
}


class MvUrlsRequest(BaseModel):
    """批量 MV 链接请求体."""

    vids: list[str] = Field(description="视频 VID 列表.")


@router.get(
    "/get_mv_urls",
    summary="获取单个 MV 播放链接",
    description="获取单个 MV 播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_urls_get(
    request: Request,
    vid: str = Query(description="视频 VID."),
):
    """获取单个 MV 播放链接."""
    client: Client = request.app.state.client
    return success_response(await client.mv.get_mv_urls([vid]))


@router.post(
    "/get_mv_urls",
    summary="批量获取 MV 播放链接",
    description="批量获取 MV 播放链接.",
    response_model=ApiResponse,
)
async def mv_get_mv_urls_post(
    request: Request,
    body: MvUrlsRequest,
):
    """批量获取 MV 播放链接."""
    client: Client = request.app.state.client
    return success_response(await client.mv.get_mv_urls(body.vids))
