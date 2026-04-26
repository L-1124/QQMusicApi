"""歌曲模块 Web 路由适配."""

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from qqmusic_api import Client, Credential
from qqmusic_api.models.song import GetSongUrlsResponse
from qqmusic_api.modules.song import BaseSongFileType, SongFileInfo, SongFileType
from web.auth import _credential_from_cookies
from web.routing import _coerce_enum_value
from web.schema import COOKIE_SECURITY_REQUIREMENT, _format_enum_values

credential_dependency = Depends(_credential_from_cookies)


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


SONG_FILE_TYPE_DESCRIPTION = f"歌曲文件类型.\n\n{_format_enum_values(BaseSongFileType)}"


def _parse_song_file_type(value: str) -> BaseSongFileType:
    """解析歌曲文件类型名称."""
    try:
        file_type = _coerce_enum_value(value, BaseSongFileType)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}") from exc
    if not isinstance(file_type, BaseSongFileType):
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}")
    return file_type


def _credential_for_request(client: Client, credential: Credential) -> Credential:
    """返回当前请求可用的登录凭证."""
    return credential if credential.musicid else client.credential


def register_song_routes(app: FastAPI) -> None:
    """注册歌曲模块 Web 适配路由."""

    @app.get(
        "/song/get_song_urls",
        tags=["song"],
        summary="获取单个歌曲文件链接",
        description="获取单个歌曲文件链接.",
        response_model=GetSongUrlsResponse,
        openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
    )
    async def song_get_song_urls_get(
        mid: str,
        file_type: str = Query(default=SongFileType.MP3_128.name, description=SONG_FILE_TYPE_DESCRIPTION),
        song_type: int | None = None,
        media_mid: str | None = None,
        credential: Credential = credential_dependency,
    ):
        client: Client = app.state.client
        target_file_type = _parse_song_file_type(file_type)
        return await client.song.get_song_urls(
            [SongFileInfo(mid=mid, file_type=target_file_type, song_type=song_type, media_mid=media_mid)],
            file_type=target_file_type,
            credential=_credential_for_request(client, credential),
        )

    @app.post(
        "/song/get_song_urls",
        tags=["song"],
        summary="批量获取歌曲文件链接",
        description="批量获取歌曲文件链接.",
        response_model=GetSongUrlsResponse,
        openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
    )
    async def song_get_song_urls_post(
        body: SongUrlsRequest,
        credential: Credential = credential_dependency,
    ):
        client: Client = app.state.client
        default_file_type = _parse_song_file_type(body.file_type)
        return await client.song.get_song_urls(
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
            credential=_credential_for_request(client, credential),
        )
