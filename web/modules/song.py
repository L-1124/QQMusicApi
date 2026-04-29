"""歌曲模块 Web 路由适配."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from qqmusic_api import Client, Credential
from qqmusic_api.modules.song import BaseSongFileType, SongFileInfo, SongFileType
from web.auth import credential_for_request, credential_from_cookies
from web.enum_utils import coerce_enum_value, iter_enum_members
from web.response import ApiResponse, success_response
from web.schema import COOKIE_SECURITY_REQUIREMENT

router = APIRouter(prefix="/song", tags=["song"])
credential_dependency = Depends(credential_from_cookies)
SONG_FILE_TYPES: tuple[BaseSongFileType, ...] = tuple(
    member for member in iter_enum_members(BaseSongFileType) if isinstance(member, BaseSongFileType)
)
DEFAULT_SONG_FILE_TYPE = SONG_FILE_TYPES.index(SongFileType.MP3_128)
SONG_FILE_TYPE_SCHEMA: dict[str, Any] = {"type": "integer", "enum": list(range(len(SONG_FILE_TYPES)))}
SONG_FILE_TYPE_DESCRIPTION = "\n".join(
    [
        "歌曲文件类型. 歌曲品质整数值映射:",
        *(
            f"- {index}: `{type(file_type).__name__}.{file_type.name.casefold()}`"
            for index, file_type in enumerate(SONG_FILE_TYPES)
        ),
    ]
)


class SongUrlItem(BaseModel):
    """单个歌曲文件链接请求项."""

    mid: str = Field(description="歌曲 MID.")
    file_type: int | SkipJsonSchema[None] = Field(
        default=None,
        description=SONG_FILE_TYPE_DESCRIPTION,
        json_schema_extra=SONG_FILE_TYPE_SCHEMA,
    )
    song_type: int | SkipJsonSchema[None] = Field(default=None, description="歌曲类型.")
    media_mid: str | SkipJsonSchema[None] = Field(default=None, description="媒体文件 MID.")


class SongUrlsRequest(BaseModel):
    """批量歌曲文件链接请求体."""

    file_info: list[SongUrlItem] = Field(description="歌曲文件信息列表.")
    file_type: int = Field(
        default=DEFAULT_SONG_FILE_TYPE,
        description=SONG_FILE_TYPE_DESCRIPTION,
        json_schema_extra=SONG_FILE_TYPE_SCHEMA,
    )


def _parse_song_file_type(value: int | str) -> BaseSongFileType:
    """解析歌曲文件类型."""
    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdecimal()):
            index = int(value)
            if 0 <= index < len(SONG_FILE_TYPES):
                return SONG_FILE_TYPES[index]
            raise KeyError(value)
        file_type = coerce_enum_value(value, BaseSongFileType)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}") from exc
    if not isinstance(file_type, BaseSongFileType):
        raise HTTPException(status_code=422, detail=f"未知歌曲文件类型: {value}")
    return file_type


def _parse_query_song_values(values: list[str]) -> list[int] | list[str]:
    """解析批量查询歌曲 ID 或 MID 列表."""
    numeric_values = [value.isdecimal() for value in values]
    if all(numeric_values):
        return [int(value) for value in values]
    if any(numeric_values):
        raise HTTPException(status_code=422, detail="value 不能混合歌曲 ID 与 MID")
    return values


@router.post(
    "/get_song_urls",
    summary="批量获取歌曲文件链接",
    description=f"批量获取歌曲文件链接.\n\n{SONG_FILE_TYPE_DESCRIPTION}",
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
                    file_type=_parse_song_file_type(item.file_type) if item.file_type is not None else None,
                    song_type=item.song_type,
                    media_mid=item.media_mid,
                )
                for item in body.file_info
            ],
            file_type=default_file_type,
            credential=credential_for_request(client, credential),
        )
    )


@router.get(
    "/{id}/fav_num",
    summary="获取歌曲收藏数量",
    description="根据单个歌曲 ID 获取收藏数量.",
    response_model=ApiResponse,
)
async def song_get_fav_num_by_id_get(
    request: Request,
    song_id: Annotated[int, Path(alias="id", description="歌曲 ID.")],
):
    """根据单个歌曲 ID 获取收藏数量."""
    client: Client = request.app.state.client
    return success_response(await client.song.get_fav_num([song_id]))


@router.get(
    "/{mid}/url",
    summary="获取单首歌曲文件链接",
    description=f"根据单个歌曲 MID 获取文件链接.\n\n{SONG_FILE_TYPE_DESCRIPTION}",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def song_get_song_url_get(
    request: Request,
    mid: Annotated[str, Path(description="歌曲 MID.")],
    file_type: int = Query(
        default=DEFAULT_SONG_FILE_TYPE,
        description=SONG_FILE_TYPE_DESCRIPTION,
        json_schema_extra=SONG_FILE_TYPE_SCHEMA,
    ),
    song_type: int | None = Query(default=None, description="歌曲类型."),
    media_mid: str | None = Query(default=None, description="媒体文件 MID."),
    credential: Credential = credential_dependency,
):
    """根据单个歌曲 MID 获取文件链接."""
    client: Client = request.app.state.client
    default_file_type = _parse_song_file_type(file_type)
    return success_response(
        await client.song.get_song_urls(
            [
                SongFileInfo(
                    mid=mid,
                    song_type=song_type,
                    media_mid=media_mid,
                )
            ],
            file_type=default_file_type,
            credential=credential_for_request(client, credential),
        )
    )


@router.get(
    "/query_song",
    summary="批量查询歌曲",
    description="根据 id 或 mid 列表批量查询歌曲.",
    response_model=ApiResponse,
)
async def song_query_song_get(
    request: Request,
    value: Annotated[list[str], Query(description="歌曲 ID 列表或 MID 列表.")],
):
    """批量查询歌曲."""
    client: Client = request.app.state.client
    return success_response(await client.song.query_song(_parse_query_song_values(value)))
