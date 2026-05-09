"""Web 层枚举值测试."""

from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from qqmusic_api.models.login import QRLoginType
from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.singer import TabType
from qqmusic_api.modules.song import BaseSongFileType, EncryptedSongFileType, SongFileType
from web.src.routing.params import (
    enum_mapping_param,
    int_enum_schema,
    iter_enum_members,
    parse_int_enum,
    parse_path_enum,
    path_enum_schema,
)
from web.src.routing.route_types import EnumIntMapping, HttpMethod, ParamOverride, ParamSource, WebRoute
from web.src.routing.router_factory import validate_routes


class _SongFileModel(BaseModel):
    """歌曲文件类型测试模型."""

    file_type: Annotated[
        BaseSongFileType, enum_mapping_param(EnumIntMapping(tuple(iter_enum_members(BaseSongFileType))))
    ]


def test_int_enum_query_schema_uses_integer_values() -> None:
    """测试 IntEnum Query 文档只暴露整数值."""
    schema = int_enum_schema(SearchType)

    assert schema == {"type": "integer", "enum": [member.value for member in SearchType]}
    assert parse_int_enum(0, SearchType) is SearchType.SONG
    assert parse_int_enum("0", SearchType) is SearchType.SONG
    with pytest.raises(TypeError, match="enum instance is not a valid external integer enum value"):
        parse_int_enum(SearchType.SONG, SearchType)
    with pytest.raises(ValueError, match="not an integer enum value"):
        parse_int_enum("song", SearchType)
    with pytest.raises(ValueError, match="not an integer enum value"):
        parse_int_enum("searchtype.song", SearchType)


def test_path_enum_schema_uses_lowercase_member_names() -> None:
    """测试 Path 枚举文档只暴露小写成员名."""
    schema = path_enum_schema(TabType)

    assert schema["type"] == "string"
    assert schema["enum"] == [member.name.casefold() for member in TabType]
    assert parse_path_enum("wiki", TabType) is TabType.WIKI
    with pytest.raises(TypeError, match="not a path enum value"):
        parse_path_enum(TabType.WIKI, TabType)
    with pytest.raises(ValueError, match="unsupported TabType"):
        parse_path_enum("tabtype.wiki", TabType)
    with pytest.raises(TypeError, match="not a path enum value"):
        parse_path_enum(("wiki", "IntroductionTab"), TabType)


def test_tuple_valued_enum_never_emits_tuple_values() -> None:
    """测试元组值枚举不会在 OpenAPI 中暴露元组值."""
    schema = path_enum_schema(TabType)

    assert all(not isinstance(value, (list, tuple)) for value in schema["enum"])


def test_non_int_enum_query_without_mapping_is_rejected() -> None:
    """测试 Query 非 IntEnum 缺少显式映射会被拒绝."""
    route = WebRoute(
        module="search",
        method="get_hotkey",
        path="/x",
        methods=(HttpMethod.GET,),
        response_model=dict,
        param_overrides=(ParamOverride("kind", ParamSource.QUERY, annotation=QRLoginType),),
    )

    errors = validate_routes((route,))

    assert any("非 IntEnum" in error for error in errors)


def test_song_file_mapping_accepts_only_stable_integer_values() -> None:
    """测试歌曲文件类型只接受稳定整数映射."""
    members = tuple(iter_enum_members(BaseSongFileType))
    mapping = EnumIntMapping(members)
    schema = mapping.schema()

    assert schema["type"] == "integer"
    assert schema["enum"] == list(range(len(members)))
    assert mapping.parse(0) is SongFileType.DTS_X
    assert mapping.parse(str(members.index(SongFileType.MP3_128))) is SongFileType.MP3_128
    assert mapping.parse(members.index(EncryptedSongFileType.FLAC)) is EncryptedSongFileType.FLAC
    assert (
        "- `25`: ENCRYPTED_FLAC"
        in EnumIntMapping(
            members,
            labels=tuple(
                member.name
                if isinstance(member, SongFileType)
                else f"{type(member).__name__.removesuffix('SongFileType').upper()}_{member.name}"
                for member in members
            ),
        ).description()
    )
    with pytest.raises(TypeError, match="not an integer enum value"):
        mapping.parse("songfiletype.mp3_128")
    with pytest.raises(TypeError, match="not an integer enum value"):
        mapping.parse("mp3_128")
    with pytest.raises(ValidationError):
        _SongFileModel(file_type="songfiletype.mp3_128")
