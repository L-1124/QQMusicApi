"""Songlist API 返回模型定义."""

from pydantic import Field

from .base import Song, SongList
from .request import Response


class SonglistCreator(Response):
    """歌单创建者信息.

    Attributes:
        musicid: 用户 musicid.
        nick: 昵称.
        headurl: 头像地址.
        encrypt_uin: 加密 UIN.
    """

    musicid: int
    nick: str = ""
    headurl: str = ""
    encrypt_uin: str = Field(default="")


class SonglistInfo(SongList):
    """歌单详情接口返回的基础元数据.

    Attributes:
        creator: 歌单创建者信息.
    """

    creator: SonglistCreator


class GetSonglistDetailResponse(Response):
    """歌单详情响应.

    该模型同时承载歌单基础信息、当前批次歌曲以及分页相关计数.

    Attributes:
        code: 返回码.
        subcode: 子返回码.
        msg: 附加消息.
        info: 歌单基础信息.
        size: 当前返回的歌曲数量.
        songs: 当前页歌曲列表.
        total: 歌单歌曲总数.
        has_more: 是否还有更多结果.
    """

    code: int = 0
    subcode: int = 0
    msg: str = ""
    info: SonglistInfo = Field(alias="dirinfo")
    size: int = Field(alias="songlist_size")
    songs: list[Song] = Field(alias="songlist")
    total: int = Field(alias="total_song_num")
    has_more: int = Field(default=0, alias="hasmore")


class CreateDeleteSonglistResp(Response):
    """创建/删除歌单响应.

    Attributes:
        retCode: 返回码 (为 0 表示成功).
        id: 创建成功的歌单 ID.
        dirid: 创建成功的歌单目录 ID.
        name: 创建成功的歌单名称.
    """

    retCode: int
    id: int = Field(json_schema_extra={"jsonpath": "$.result.tid"})
    dirid: int = Field(json_schema_extra={"jsonpath": "$.result.dirId"})
    name: str = Field(json_schema_extra={"jsonpath": "$.result.dirName"})
