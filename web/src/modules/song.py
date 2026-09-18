"""歌曲模块 Web 路由适配."""

from typing import Annotated, Any, TypeAlias

from pydantic import BaseModel, BeforeValidator, Field, WithJsonSchema, model_validator
from pydantic.json_schema import SkipJsonSchema
from typing_extensions import Self

from qqmusic_api.modules.song import (
    BaseSongFileType,
    EncryptedSongFileType,
    RingSongFileType,
    SongApi,
    SongFileInfo,
    SongFileType,
    SongQueryInfo,
    SpecialSongFileType,
)

from ..routing.adapter_registry import adapter
from ..routing.docstrings import get_enum_member_descriptions
from ..routing.params import enum_mapping_schema, enum_mapping_validator
from ..routing.route_types import EnumIntMapping, RouteContext

_APPENDED_SONG_FILE_TYPES: tuple[BaseSongFileType, ...] = (SpecialSongFileType.TRY_OGG_640,)
SONG_FILE_TYPES: tuple[BaseSongFileType, ...] = (
    tuple(
        member
        for enum_type in (SongFileType, EncryptedSongFileType, SpecialSongFileType, RingSongFileType)
        for member in enum_type
        if member not in _APPENDED_SONG_FILE_TYPES
    )
    + _APPENDED_SONG_FILE_TYPES
)
SONG_FILE_TYPE_DESCRIPTIONS = tuple(
    get_enum_member_descriptions(type(member)).get(member.name, "") for member in SONG_FILE_TYPES
)

SONG_FILE_TYPE_MAPPING = EnumIntMapping(SONG_FILE_TYPES, descriptions=SONG_FILE_TYPE_DESCRIPTIONS)
SongFileTypeParam: TypeAlias = Annotated[
    Any,
    BeforeValidator(enum_mapping_validator(SONG_FILE_TYPE_MAPPING)),
    WithJsonSchema(enum_mapping_schema(SONG_FILE_TYPE_MAPPING)),
]
SONG_FILE_TYPE_LABEL = "歌曲文件类型."
SONG_FILE_TYPE_DESCRIPTION = f"{SONG_FILE_TYPE_LABEL}\n\n{SONG_FILE_TYPE_MAPPING.description()}"


class SongUrlItem(BaseModel):
    """单个歌曲文件链接请求项."""

    mid: str = Field(description="歌曲 MID.")
    file_type: SongFileTypeParam | SkipJsonSchema[None] = Field(
        default=None,
        description=SONG_FILE_TYPE_DESCRIPTION,
    )
    song_type: int | SkipJsonSchema[None] = Field(default=None, description="歌曲类型.")
    media_mid: str | SkipJsonSchema[None] = Field(default=None, description="媒体文件 MID.")

    def to_sdk(self) -> SongFileInfo:
        """转换为 SDK 请求项."""
        return SongFileInfo(
            mid=self.mid,
            file_type=self.file_type,
            song_type=self.song_type,
            media_mid=self.media_mid,
        )


class SongUrlsRequest(BaseModel):
    """批量歌曲文件链接请求体."""

    file_info: list[SongUrlItem] = Field(max_length=SongApi._GET_SONG_URLS_MAX_MID, description="歌曲文件信息列表.")
    file_type: SongFileTypeParam = Field(
        default=SONG_FILE_TYPES.index(SongFileType.MP3_128),
        validate_default=True,
        description=SONG_FILE_TYPE_DESCRIPTION,
    )


class SongQueryItem(BaseModel):
    """单个歌曲查询项."""

    id: int | SkipJsonSchema[None] = Field(default=None, description="歌曲 ID.")
    mid: str | SkipJsonSchema[None] = Field(default=None, description="歌曲 MID.")
    song_type: int | SkipJsonSchema[None] = Field(default=None, description="歌曲类型.")

    def to_sdk(self) -> SongQueryInfo:
        """转换为 SDK 查询项."""
        return SongQueryInfo(id=self.id, mid=self.mid, song_type=self.song_type)

    @model_validator(mode="after")
    def _require_single_identifier(self) -> Self:
        """校验 id 与 mid 必须二选一."""
        if (self.id is None) == (self.mid is None):
            raise ValueError("必须提供 id 或 mid 且不能同时提供")
        return self


class QuerySongRequest(BaseModel):
    """批量歌曲查询请求体."""

    query_info: list[SongQueryItem] = Field(min_length=1, description="歌曲查询信息列表.")


@adapter("song", "get_song_urls")
async def get_song_urls_adapter(context: RouteContext):
    """批量获取歌曲文件链接."""
    body = context.params["body"]
    return await context.execute_module(
        SongApi,
        SongApi.get_song_urls,
        file_info=[item.to_sdk() for item in body.file_info],
        file_type=body.file_type,
        credential=context.credential,
    )


@adapter("song", "get_fav_num_by_id")
async def get_fav_num_by_id_adapter(context: RouteContext):
    """根据单个歌曲 ID 获取收藏数量."""
    return await context.execute_module(
        SongApi,
        SongApi.get_fav_num,
        song_ids=[context.params["id"]],
    )


@adapter("song", "get_song_url")
async def get_song_url_adapter(context: RouteContext):
    """根据单个歌曲 MID 获取文件链接."""
    return await context.execute_module(
        SongApi,
        SongApi.get_song_urls,
        file_info=[
            SongUrlItem(
                mid=context.params["mid"],
                song_type=context.params.get("song_type"),
                media_mid=context.params.get("media_mid"),
            ).to_sdk()
        ],
        file_type=context.params["file_type"],
        credential=context.credential,
    )


@adapter("song", "query_song_get")
async def query_song_get_adapter(context: RouteContext):
    """获取单首歌曲信息."""
    value = context.params["value"]
    song_type = context.params.get("song_type")
    is_id = value.isdecimal()
    query_info = SongQueryItem(
        id=int(value) if is_id else None,
        mid=None if is_id else value,
        song_type=song_type,
    ).to_sdk()
    return await context.execute_module(
        SongApi,
        SongApi.query_song,
        song_info=[query_info],
    )


@adapter("song", "query_song_post")
async def query_song_post_adapter(context: RouteContext):
    """批量查询歌曲."""
    body = context.params["body"]
    query_info = [item.to_sdk() for item in body.query_info]
    return await context.execute_module(
        SongApi,
        SongApi.query_song,
        song_info=query_info,
    )
