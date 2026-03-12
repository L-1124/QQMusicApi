"""歌手相关 API."""

from enum import Enum
from typing import cast

from ._base import ApiModule


class AreaType(Enum):
    """地区类型枚举."""

    ALL = -100
    CHINA = 200
    TAIWAN = 2
    AMERICA = 5
    JAPAN = 4
    KOREA = 3


class GenreType(Enum):
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


class SexType(Enum):
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


class IndexType(Enum):
    """首字母索引枚举."""

    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9  # noqa: E741
    J = 10
    K = 11
    L = 12
    M = 13
    N = 14
    O = 15  # noqa: E741
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


def validate_int_enum(value: int | Enum, enum_type: type[Enum]) -> int:
    """确保输入值符合枚举定义.

    Args:
        value: 待校验的值或枚举成员.
        enum_type: 目标枚举类.

    Returns:
        int: 对应的整型数值.

    Raises:
        ValueError: 如果值不在枚举定义中.
    """
    if isinstance(value, enum_type):
        return cast("int", value.value)
    if value in {item.value for item in enum_type}:
        return cast("int", value)
    raise ValueError(f"Invalid value: {value} for {enum_type.__name__}")


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
        return self._build_request(
            module="music.musichallSinger.SingerList",
            method="GetSingerList",
            param={
                "hastag": 0,
                "area": validate_int_enum(area, AreaType),
                "sex": validate_int_enum(sex, SexType),
                "genre": validate_int_enum(genre, GenreType),
            },
        )

    def get_singer_list_index(
        self,
        area: int | AreaType = AreaType.ALL,
        sex: int | SexType = SexType.ALL,
        genre: int | GenreType = GenreType.ALL,
        index: int | IndexType = IndexType.ALL,
        sin: int = 0,
        cur_page: int = 1,
    ):
        """获取按索引分页的歌手列表原始数据.

        Args:
            area: 地区类型.
            sex: 性别类型.
            genre: 风格类型.
            index: 首字母索引.
            sin: 起始位置.
            cur_page: 当前页码.
        """
        return self._build_request(
            module="music.musichallSinger.SingerList",
            method="GetSingerListIndex",
            param={
                "area": validate_int_enum(area, AreaType),
                "sex": validate_int_enum(sex, SexType),
                "genre": validate_int_enum(genre, GenreType),
                "index": validate_int_enum(index, IndexType),
                "sin": sin,
                "cur_page": cur_page,
            },
        )

    def get_info(self, mid: str):
        """获取歌手主页基本信息.

        Args:
            mid: 歌手 MID.
        """
        return self._build_request(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"SingerMid": mid},
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
        return self._build_request(
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
        )

    def get_desc(self, mids: list[str]):
        """获取歌手列表的描述信息.

        Args:
            mids: 歌手 MID 列表.
        """
        return self._build_request(
            module="music.musichallSinger.SingerInfoInter",
            method="GetSingerDetail",
            param={"singer_mids": mids, "groups": 1, "wikis": 1},
        )

    def get_similar(self, mid: str, number: int = 10):
        """获取相似歌手列表.

        Args:
            mid: 歌手 MID.
            number: 返回相似歌手的数量.
        """
        return self._build_request(
            module="music.SimilarSingerSvr",
            method="GetSimilarSingerList",
            param={"singerMid": mid, "number": number},
        )

    def get_songs_list(self, mid: str, number: int = 10, begin: int = 0):
        """获取歌手的歌曲列表.

        Args:
            mid: 歌手 MID.
            number: 返回歌曲数量.
            begin: 分页起始位置.
        """
        return self._build_request(
            module="musichall.song_list_server",
            method="GetSingerSongList",
            param={"singerMid": mid, "order": 1, "number": number, "begin": begin},
        )

    def get_album_list(self, mid: str, number: int = 10, begin: int = 0):
        """获取歌手的专辑列表.

        Args:
            mid: 歌手 MID.
            number: 返回专辑数量.
            begin: 分页起始位置.
        """
        return self._build_request(
            module="music.musichallAlbum.AlbumListServer",
            method="GetAlbumList",
            param={"singerMid": mid, "order": 1, "number": number, "begin": begin},
        )

    def get_mv_list(self, mid: str, number: int = 10, begin: int = 0):
        """获取歌手 MV 列表数据.

        Args:
            mid: 歌手 MID.
            number: 返回数量.
            begin: 起始位置.
        """
        return self._build_request(
            module="MvService.MvInfoProServer",
            method="GetSingerMvList",
            param={"singermid": mid, "order": 1, "count": number, "start": begin},
        )
