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
    time_public: str = Field(default="", validation_alias="publishDate")
    desc: str = ""
    language: str = ""
    album_type: str = Field(default="", validation_alias="albumType")
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

    id: int = Field(validation_alias="ID")
    name: str
    is_show: int = Field(validation_alias="isShow")
    brief: str = ""


class GetAlbumDetailResponse(Response):
    """专辑详情接口聚合后的响应体.

    Attributes:
        album: 专辑基础信息与补充描述.
        company: 发行公司信息.
        singers: 专辑署名歌手列表.
    """

    album: AlbumDetail = Field(validation_alias="basicInfo")
    company: AlbumCompany
    singers: list[Singer] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.singer.singerList"})


class GetAlbumSongResponse(Response):
    """专辑歌曲列表接口返回的分页结果.

    Attributes:
        album_mid: 专辑 MID.
        total_num: 歌曲总数.
        song_list: 当前响应携带的专辑歌曲列表.
    """

    album_mid: str = Field(validation_alias="albumMid")
    total_num: int = Field(validation_alias="totalNum")
    song_list: list[Song] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.songList[*].songInfo"})


class NewAlbumItem(Album):
    """新碟上架列表中的单张专辑摘要.

    Attributes:
        singers: 专辑署名歌手列表.
        release_time: 发行日期, 格式通常为 YYYY-MM-DD.
        type: 专辑类型.
        area: 地区标识.
        genre: 流派标识.
        language: 语种标识.
    """

    singers: list[Singer] = Field(default_factory=list)
    release_time: str = ""
    type: int = 0
    area: int = 0
    genre: int = 0
    language: int = 0


class GetNewAlbumResponse(Response):
    """新碟上架接口的响应体.

    Attributes:
        total: 该地区下新碟总数.
        albums: 当前页新碟列表.
    """

    total: int = 0
    albums: list[NewAlbumItem] = Field(default_factory=list)


class AlbumFavWriteResponse(Response):
    """收藏 / 取消收藏专辑的写操作响应.

    Attributes:
        result: 操作结果码, 0 表示成功.
        failed_album_id: 操作失败的专辑 ID 列表, 全部成功时为空.
    """

    result: int = 0
    failed_album_id: list[int] = Field(default_factory=list, validation_alias="v_failedAlbumId")

    @property
    def success(self) -> bool:
        """是否操作成功 (result 为 0 且无失败项)."""
        return self.result == 0 and not self.failed_album_id
