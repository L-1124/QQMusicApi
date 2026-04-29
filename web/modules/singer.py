"""歌手模块 Web 路由适配."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Path, Request

from web.response import ApiResponse, success_response

if TYPE_CHECKING:
    from qqmusic_api import Client

router = APIRouter(prefix="/singer", tags=["singer"])


@router.get(
    "/{mid}/desc",
    summary="获取歌手描述",
    description="根据单个歌手 MID 获取描述信息.",
    response_model=ApiResponse,
)
async def singer_get_desc_by_mid_get(
    request: Request,
    mid: Annotated[str, Path(description="歌手 MID.")],
):
    """根据单个歌手 MID 获取描述信息."""
    client: Client = request.app.state.client
    return success_response(await client.singer.get_desc([mid]))
