"""歌手模块 Web 路由适配."""

from typing import Annotated

from fastapi import APIRouter, Path

from qqmusic_api import Client
from web.deps import client_dependency
from web.response import ApiResponse, success_response

router = APIRouter(prefix="/singer", tags=["singer"])


@router.get(
    "/{mid}/desc",
    summary="获取歌手描述",
    description="根据单个歌手 MID 获取描述信息.",
    response_model=ApiResponse,
)
async def singer_get_desc_by_mid_get(
    mid: Annotated[str, Path(description="歌手 MID.")],
    client: Client = client_dependency,
):
    """根据单个歌手 MID 获取描述信息."""
    return success_response(await client.singer.get_desc([mid]))
