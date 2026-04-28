"""歌曲模块 Web 路由适配."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from qqmusic_api import Client, Credential
from qqmusic_api.modules.song import BaseSongFileType, SongFileInfo, SongFileType
from web.auth import credential_for_request, credential_from_cookies
from web.enum_utils import coerce_enum_value
from web.response import ApiResponse, success_response
from web.schema import COOKIE_SECURITY_REQUIREMENT

router = APIRouter(prefix="/song", tags=["song"])
credential_dependency = Depends(credential_from_cookies)


class SongUrlItem(BaseModel):
    """单个歌曲文件链接请求项."""

    mid: str = Field(description="歌曲 MID.")
    file_type: str | SkipJsonSchema[None] = Field(default=None, description="歌曲文件类型.")
    song_type: int | SkipJsonSchema[None] = Field(default=None, description="歌曲类型.")
    media_mid: str | SkipJsonSchema[None] = Field(default=None, description="媒体文件 MID.")


class SongUrlsRequest(BaseModel):
    """批量歌曲文件链接请求体."""

    file_info: list[SongUrlItem] = Field(description="歌曲文件信息列表.")
    file_type: str = Field(default=SongFileType.MP3_128.name, description="默认歌曲文件类型.")


class QuerySongRequest(BaseModel):
    """批量查询歌曲请求体."""

    value: list[int] | list[str] = Field(description="歌曲 ID 列表或 MID 列表.")


def _parse_song_file_type(value: str) -> BaseSongFileType:
    """解析歌曲文件类型名称."""
    try:
        file_type = coerce_enum_value(value, BaseSongFileType)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}") from exc
    if not isinstance(file_type, BaseSongFileType):
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}")
    return file_type


@router.post(
    "/get_song_urls",
    summary="批量获取歌曲文件链接",
    description="批量获取歌曲文件链接.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def song_get_song_urls_post(
    request: Request,
    body: SongUrlsRequest,
    credential: Credential = credential_dependency,
):
    """批量获取歌曲文件链接."""
    client: Client = request.app.state.client
    default_file_type = _parse_song_file_type(body.file_type)
    return success_response(
        await client.song.get_song_urls(
            [
                SongFileInfo(
                    mid=item.mid,
                    file_type=_parse_song_file_type(item.file_type) if item.file_type else None,
                    song_type=item.song_type,
                    media_mid=item.media_mid,
                )
                for item in body.file_info
            ],
            file_type=default_file_type,
            credential=credential_for_request(client, credential),
        )
    )


@router.post(
    "/query_song",
    summary="批量查询歌曲",
    description="根据 id 或 mid 列表批量查询歌曲.",
    response_model=ApiResponse,
)
async def song_query_song_post(
    request: Request,
    body: QuerySongRequest,
):
    """批量查询歌曲."""
    client: Client = request.app.state.client
    return success_response(await client.song.query_song(body.value))
