"""Album API 返回模型定义."""

from pydantic import Field

from .base import Album, Singer, Song
from .request import Response


class AlbumDetail(Album):
    """专辑详情页返回的核心专辑信息.

    Attributes:
        subtitle: 专辑副标题.
        time_public: 发行日期.
        desc: 专辑简介.
        language: 专辑语种.
        album_type: 专辑类型描述.
        genre: 专辑流派文本.
        wikiurl: 百科链接.
    """

    subtitle: str = ""
    time_public: str = Field(default="", alias="publishDate")
    desc: str = ""
    language: str = ""
    album_type: str = Field(default="", alias="albumType")
    genre: str = ""
    wikiurl: str = ""


class AlbumCompany(Response):
    """专辑详情接口中的发行公司信息.

    Attributes:
        id: 公司 ID.
        name: 公司名称.
        is_show: 是否展示.
        brief: 公司简介.
    """

    id: int = Field(alias="ID")
    name: str
    is_show: int = Field(alias="isShow")
    brief: str = ""


class GetAlbumDetailResponse(Response):
    """专辑详情接口聚合后的响应体.

    Attributes:
        album: 专辑基础信息与补充描述.
        company: 发行公司信息.
        singers: 专辑署名歌手列表.
    """

    album: AlbumDetail = Field(alias="basicInfo")
    company: AlbumCompany
    singers: list[Singer] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.singer.singerList"})


class GetAlbumSongResponse(Response):
    """专辑歌曲列表接口返回的分页结果.

    Attributes:
        album_mid: 专辑 MID.
        total_num: 歌曲总数.
        song_list: 当前响应携带的专辑歌曲列表.
    """

    album_mid: str = Field(alias="albumMid")
    total_num: int = Field(alias="totalNum")
    song_list: list[Song] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.songList[*].songInfo"})
