"""歌手相关 API."""

from enum import Enum, IntEnum
from typing import cast

from ..core import Platform
from ..core.pagination import (
    MultiFieldContinuationStrategy,
    OffsetStrategy,
    PageStrategy,
)
from ..models.singer import (
    HomepageHeaderResponse,
    HomepageTabDetailResponse,
    SimilarSingerResponse,
    SingerAlbumListResponse,
    SingerDetailResponse,
    SingerIndexPageResponse,
    SingerMvListResponse,
    SingerNameSpecialDisplayResponse,
    SingerSongListResponse,
    SingerTypeListResponse,
)
from ._base import ApiModule


class AreaType(IntEnum):
    """地区类型枚举."""

    ALL = -100
    CHINA = 200
    TAIWAN = 2
    AMERICA = 5
    JAPAN = 4
    KOREA = 3


class GenreType(IntEnum):
    """风格类型枚举."""

    ALL = -100
    POP = 7
    RAP = 3
    CHINESE_STYLE = 19
    ROCK = 4
    ELECTRONIC = 2
    FOLK = 8
    R_AND_B = 11
    ETHNIC = 37
    LIGHT_MUSIC = 93
    JAZZ = 14
    CLASSICAL = 33
    COUNTRY = 13
    BLUES = 10


class SexType(IntEnum):
    """性别类型枚举."""

    ALL = -100
    MALE = 0
    FEMALE = 1
    GROUP = 2


class TabType(Enum):
    """歌手主页 Tab 枚举."""

    WIKI = ("wiki", "IntroductionTab")
    ALBUM = ("album", "AlbumTab")
    COMPOSER = ("song_composing", "SongTab")
    LYRICIST = ("song_lyric", "SongTab")
    PRODUCER = ("producer", "SongTab")
    ARRANGER = ("arranger", "SongTab")
    MUSICIAN = ("musician", "SongTab")
    SONG = ("song_sing", "SongTab")
    VIDEO = ("video", "VideoTab")

    def __init__(self, tab_id: str, tab_name: str) -> None:
        """初始化歌手主页 Tab 类型.

        Args:
            tab_id: Tab 标识符.
            tab_name: Tab 名称.
        """
        self.tab_id = tab_id
        self.tab_name = tab_name


class IndexType(IntEnum):
    """首字母索引枚举."""

    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9
    J = 10
    K = 11
    L = 12
    M = 13
    N = 14
    O = 15
    P = 16
    Q = 17
    R = 18
    S = 19
    T = 20
    U = 21
    V = 22
    W = 23
    X = 24
    Y = 25
    Z = 26
    ALL = -100
    HASH = 27


class SingerApi(ApiModule):
    """歌手相关 API."""

    def get_singer_list(
        self,
        area: int | AreaType = AreaType.ALL,
        sex: int | SexType = SexType.ALL,
        genre: int | GenreType = GenreType.ALL,
    ):
        """获取歌手列表原始数据.

        Args:
            area: 地区类型.
            sex: 性别类型.
            genre: 风格类型.
        """
        return self._build_cgi(
            module="music.musichallSinger.SingerList",
            method="GetSingerList",
            param={
                "hastag": 0,
                "area": int(AreaType(area)),
                "sex": int(SexType(sex)),
                "genre": int(GenreType(genre)),
            },
            response_model=SingerTypeListResponse,
        )

    def get_singer_list_index(
        self,
        area: int | AreaType = AreaType.ALL,
        sex: int | SexType = SexType.ALL,
        genre: int | GenreType = GenreType.ALL,
        index: int | IndexType = IndexType.ALL,
        page: int = 1,
        num: int = 80,
    ):
        """获取按索引分页的歌手列表原始数据.

        Args:
            area: 地区类型.
            sex: 性别类型.
            genre: 风格类型.
            index: 首字母索引.
            page: 页码.
            num: 每页返回数量.
        """
        return self._build_cgi(
            module="music.musichallSinger.SingerList",
            method="GetSingerListIndex",
            param={
                "area": int(AreaType(area)),
                "sex": int(SexType(sex)),
                "genre": int(GenreType(genre)),
                "index": int(IndexType(index)),
                "sin": (page - 1) * num,
                "cur_page": page,
            },
            response_model=SingerIndexPageResponse,
            pager_strategy=MultiFieldContinuationStrategy[SingerIndexPageResponse](
                lambda params, response: (
                    None
                    if not response.singerlist or params["sin"] + len(response.singerlist) >= (response.total or 0)
                    else {
                        **cast("dict[str, int]", params),
                        "sin": cast("dict[str, int]", params)["sin"] + len(response.singerlist),
                        "cur_page": cast("dict[str, int]", params)["cur_page"] + 1,
                    }
                ),
                context_name="singer_list_index",
            ),
        ).with_extractor(lambda r: r.singerlist)

    def get_info(self, mid: str):
        """获取歌手主页基本信息.

        固定使用 Android 平台.

        Args:
            mid: 歌手 MID.
        """
        return self._build_cgi(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"SingerMid": mid},
            response_model=HomepageHeaderResponse,
            platform=Platform.ANDROID,
        )

    def get_name_special_display(self, mid: str):
        """获取歌手名称透明 PNG 展示信息.

        返回歌手名称、展示类型、图片地址和重叠比例.
        无名称图片时, 返回 display_type=0 和空 pic_file.

        Args:
            mid: 歌手 MID.
        """
        return self._build_cgi(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"SingerMid": mid},
            response_model=SingerNameSpecialDisplayResponse,
            platform=Platform.ANDROID,
            comm={"cv": 20_080_000, "v": 20_080_000},
        )

    def get_tab_detail(
        self,
        mid: str,
        tab_type: TabType,
        page: int = 1,
        num: int = 10,
    ):
        """获取歌手主页特定 Tab 的详情原始数据.

        Args:
            mid: 歌手 MID.
            tab_type: Tab 类型.
            page: 页码.
            num: 返回数量.
        """
        return self._build_cgi(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageTabDetail",
            param={
                "SingerMid": mid,
                "IsQueryTabDetail": 1,
                "TabID": tab_type.tab_id,
                "PageNum": page - 1,
                "PageSize": num,
                "Order": 0,
            },
            response_model=HomepageTabDetailResponse,
            pager_strategy=PageStrategy[HomepageTabDetailResponse](
                page_key="PageNum",
                page_size=num,
                start_page=page - 1,
                has_more_extractor=lambda response: bool(response.has_more),
            ),
        )

    def get_desc(
        self,
        mids: list[str],
        *,
        ex_singer: bool = True,
        wiki_singer: bool = True,
        group_singer: bool = True,
        pic: bool = True,
        photos: bool = True,
    ):
        """获取歌手列表的描述信息.

        Args:
            mids: 歌手 MID 列表.
            ex_singer: 是否返回扩展描述信息.
            wiki_singer: 是否返回百科 XML 数据.
            group_singer: 是否返回组合成员信息.
            pic: 是否返回头像/立绘图片 URL.
            photos: 是否返回相册大图列表.
        """
        return self._build_cgi(
            module="music.musichallSinger.SingerInfoInter",
            method="GetSingerDetail",
            param={
                "singer_mids": mids,
                "group_singer": group_singer,
                "wiki_singer": wiki_singer,
                "ex_singer": ex_singer,
                "pic": pic,
                "photos": photos,
            },
            response_model=SingerDetailResponse,
        )

    def get_similar(self, mid: str, number: int = 10):
        """获取相似歌手列表.

        Args:
            mid: 歌手 MID.
            number: 返回相似歌手的数量.
        """
        return self._build_cgi(
            module="music.SimilarSingerSvr",
            method="GetSimilarSingerList",
            param={"singerMid": mid, "number": number},
            response_model=SimilarSingerResponse,
        )

    def get_songs_list(self, mid: str, num: int = 10, page: int = 1):
        """获取歌手的歌曲列表.

        Args:
            mid: 歌手 MID.
            num: 返回歌曲数量.
            page: 分页页码.
        """
        return self._build_cgi(
            module="musichall.song_list_server",
            method="GetSingerSongList",
            param={"singerMid": mid, "order": 1, "number": num, "begin": (page - 1) * num},
            response_model=SingerSongListResponse,
            pager_strategy=OffsetStrategy[SingerSongListResponse](
                offset_key="begin",
                page_size_key="number",
                total_extractor=lambda r: r.total_num,
                count_extractor=lambda r: len(r.song_list),
            ),
        ).with_extractor(lambda response: response.song_list)

    def get_album_list(self, mid: str, num: int = 10, page: int = 1):
        """获取歌手的专辑列表.

        Args:
            mid: 歌手 MID.
            num: 返回专辑数量.
            page: 分页页码.
        """
        return self._build_cgi(
            module="music.musichallAlbum.AlbumListServer",
            method="GetAlbumList",
            param={"singerMid": mid, "order": 1, "number": num, "begin": (page - 1) * num},
            response_model=SingerAlbumListResponse,
            pager_strategy=OffsetStrategy[SingerAlbumListResponse](
                offset_key="begin",
                page_size_key="number",
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.album_list),
            ),
        ).with_extractor(lambda r: r.album_list)

    def get_mv_list(self, mid: str, num: int = 10, page: int = 1):
        """获取歌手 MV 列表数据.

        Args:
            mid: 歌手 MID.
            num: 返回数量.
            page: 分页页码.
        """
        return self._build_cgi(
            module="MvService.MvInfoProServer",
            method="GetSingerMvList",
            param={"singermid": mid, "order": 1, "count": num, "start": (page - 1) * num},
            response_model=SingerMvListResponse,
            pager_strategy=OffsetStrategy[SingerMvListResponse](
                offset_key="start",
                page_size_key="count",
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.mv_list),
            ),
        ).with_extractor(lambda r: r.mv_list)
