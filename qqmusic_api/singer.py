"""歌手相关 API"""

from enum import Enum
from typing import Any, Literal, cast

from .utils.network import NO_PROCESSOR, RequestGroup, api_request


class AreaType(Enum):
    """地区类型枚举"""

    ALL = -100
    CHINA = 200
    TAIWAN = 2
    AMERICA = 5
    JAPAN = 4
    KOREA = 3


class GenreType(Enum):
    """风格类型枚举"""

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
    """性别类型枚举"""

    ALL = -100
    MALE = 0
    FEMALE = 1
    GROUP = 2


class TabType(Enum):
    """Tab 类型枚举"""

    WIKI = ("wiki", "IntroductionTab")
    ALBUM = ("album", "AlbumTab")
    COMPOSER = ("song_composing", "SongTab")
    LYRICIST = ("song_lyric", "SongTab")
    PRODUCER = ("producer", "SongTab")
    ARRANGER = ("arranger", "SongTab")
    MUSICIAN = ("musician", "SongTab")
    SONG = ("song_sing", "SongTab")
    VIDEO = ("video", "VideoTab")

    def __init__(self, tab_id: str, tab_name: str):
        self.tab_id = tab_id
        self.tab_name = tab_name


class IndexType(Enum):
    """首字母索引枚举"""

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
    """确保传入的值符合指定的枚举类型"""
    if isinstance(value, enum_type):
        return value.value  # 如果是枚举成员,返回对应的整数值
    if value in {item.value for item in enum_type}:
        return cast(int, value)  # 如果是合法整数值,直接返回
    raise ValueError(f"Invalid value: {value} for {enum_type.__name__}")


@api_request("music.musichallSinger.SingerList", "GetSingerList")
async def get_singer_list(
    area: int | AreaType = AreaType.ALL,
    sex: int | SexType = SexType.ALL,
    genre: int | GenreType = GenreType.ALL,
):
    """获取歌手列表

    Args:
        area: 地区
        sex: 性别
        genre: 风格
    """
    area = validate_int_enum(area, AreaType)
    sex = validate_int_enum(sex, SexType)
    genre = validate_int_enum(genre, GenreType)

    return {
        "hastag": 0,
        "area": area,
        "sex": sex,
        "genre": genre,
    }, lambda data: cast(
        list[dict[str, Any]],
        data["hotlist"],
    )


@api_request("music.musichallSinger.SingerList", "GetSingerListIndex", catch_error_code=[104500])
async def get_singer_list_index(
    area: int | AreaType = AreaType.ALL,
    sex: int | SexType = SexType.ALL,
    genre: int | GenreType = GenreType.ALL,
    index: int | IndexType = IndexType.ALL,
    sin: int = 0,
    cur_page: int = 1,
):
    """获取歌手列表原始数据

    Args:
        area: 地区
        sex: 性别
        genre: 风格
        index: 索引
        sin: 跳过数量
        cur_page: 当前页
    """
    area = validate_int_enum(area, AreaType)
    sex = validate_int_enum(sex, SexType)
    genre = validate_int_enum(genre, GenreType)
    index = validate_int_enum(index, IndexType)

    return {
        "area": area,
        "sex": sex,
        "genre": genre,
        "index": index,
        "sin": sin,
        "cur_page": cur_page,
    }, NO_PROCESSOR


async def get_singer_list_index_all(
    area: int | AreaType = AreaType.ALL,
    sex: int | SexType = SexType.ALL,
    genre: int | GenreType = GenreType.ALL,
    index: int | IndexType = IndexType.ALL,
) -> list[dict[str, Any]]:
    """获取所有歌手列表

    Args:
        area: 地区
        sex: 性别
        genre: 风格
        index: 索引
    """
    area = validate_int_enum(area, AreaType)
    sex = validate_int_enum(sex, SexType)
    genre = validate_int_enum(genre, GenreType)
    index = validate_int_enum(index, IndexType)

    data = await get_singer_list_index(area=area, sex=sex, genre=genre, index=index, sin=0, cur_page=1)

    singer_list = data["singerlist"]
    total = data["total"]
    if total <= 80:
        return cast(list[dict[str, Any]], singer_list)

    # 每页80个歌手,向下取整
    pages = total // 80
    sin = 80
    rg = RequestGroup()
    for page in range(2, pages + 2):
        rg.add_request(get_singer_list_index, area=area, sex=sex, genre=genre, index=index, sin=sin, cur_page=page)
        sin += 80

    for data in await rg.execute():
        singer_list.extend(data["singerlist"])
    return singer_list


@api_request("music.UnifiedHomepage.UnifiedHomepageSrv", "GetHomepageHeader")
async def get_info(mid: str):
    """获取歌手基本信息

    Args:
        mid: 歌手 mid
    """
    return {"SingerMid": mid}, NO_PROCESSOR


@api_request("music.UnifiedHomepage.UnifiedHomepageSrv", "GetHomepageTabDetail")
async def get_tab_detail(mid: str, tab_type: TabType, page: int = 1, num: int = 10):
    """获取歌手 Tab 详细信息

    Args:
        mid: 歌手 mid
        tab_type: Tab 类型
        page: 页码
        num: 返回数量
    """
    params = {
        "SingerMid": mid,
        "IsQueryTabDetail": 1,
        "TabID": tab_type.tab_id,
        "PageNum": page - 1,
        "PageSize": num,
        "Order": 0,
    }

    def _processor(data: dict[str, Any]) -> list[dict[str, Any]]:
        data = data[tab_type.tab_name]
        return data.get("List") or data.get("VideoList") or data.get("AlbumList") or []

    return params, _processor


@api_request("music.musichallSinger.SingerInfoInter", "GetSingerDetail")
async def get_desc(mids: list[str]):
    """获取歌手简介

    Args:
        mids: 歌手 mid 列表
    """
    return {"singer_mids": mids, "groups": 1, "wikis": 1}, lambda data: cast(list[dict[str, Any]], data["singer_list"])


@api_request("music.SimilarSingerSvr", "GetSimilarSingerList")
async def get_similar(mid: str, number: int = 10):
    """获取类似歌手列表

    Args:
        mid: 歌手 mid
        number: 类似歌手数量
    """
    return {"singerMid": mid, "number": number}, lambda data: cast(list[dict[str, Any]], data["singerlist"])


async def get_songs(
    mid: str,
    tab_type: Literal[
        TabType.SONG,
        TabType.ALBUM,
        TabType.COMPOSER,
        TabType.LYRICIST,
        TabType.PRODUCER,
        TabType.ARRANGER,
        TabType.MUSICIAN,
    ] = TabType.SONG,
    page: int = 1,
    num: int = 10,
) -> list[dict[str, Any]]:
    """获取歌手歌曲

    Args:
        mid: 歌手 mid
        tab_type: Tab 类型
        page: 页码
        num:  返回数量
    """
    return await get_tab_detail(mid, tab_type, page, num)


@api_request("musichall.song_list_server", "GetSingerSongList")
async def get_songs_list(mid: str, number: int = 10, begin: int = 0):
    """获取歌手歌曲原始数据

    Args:
        mid: 歌手 mid
        number: 每次获取数量,最大30
        begin: 从第几个开始
    """
    return {
        "singerMid": mid,
        "order": 1,
        "number": number,
        "begin": begin,
    }, NO_PROCESSOR


async def get_songs_list_all(mid: str) -> list[dict[str, Any]]:
    """获取歌手所有歌曲列表

    Args:
        mid: 歌手 mid
    """
    response = await get_songs_list(mid=mid, number=30, begin=0)

    total = response["totalNum"]
    songs = [song["songInfo"] for song in response["songList"]]
    if total <= 30:
        return cast(list[dict[str, Any]], songs)

    rg = RequestGroup()
    for num in range(30, total, 30):
        rg.add_request(get_songs_list, mid=mid, number=30, begin=num)

    response = await rg.execute()
    for res in response:
        songs.extend([song["songInfo"] for song in res["songList"]])

    return songs


@api_request("music.musichallAlbum.AlbumListServer", "GetAlbumList")
async def get_album_list(mid: str, number: int = 10, begin: int = 0):
    """获取歌手专辑

    Args:
        mid: 歌手 mid
        number: 每次获取数量,不足30个的时候直接全部返回
        begin: 从第几个开始
    """
    return {
        "singerMid": mid,
        "order": 1,
        "number": number,
        "begin": begin,
    }, NO_PROCESSOR


async def get_album_list_all(mid: str) -> list[dict[str, Any]]:
    """获取歌手所有专辑列表

    Args:
        mid: 歌手 mid
    """
    response = await get_album_list(mid=mid, number=30, begin=0)

    total = response["total"]
    albums = response["albumList"]
    if total <= 30:
        return cast(list[dict[str, Any]], albums)

    rg = RequestGroup()
    for num in range(30, total, 30):
        rg.add_request(get_album_list, mid=mid, number=30, begin=num)

    response = await rg.execute()
    for res in response:
        albums.extend(res["albumList"])

    return albums


@api_request("MvService.MvInfoProServer", "GetSingerMvList")
async def get_mv_list(mid: str, number: int = 10, begin: int = 0):
    """获取歌手mv原始数据

    Args:
        mid: 歌手 mid
        number: 每次获取数量,每次最大100
        begin: 从第几个开始
    """
    return {
        "singermid": mid,
        "order": 1,
        "count": number,
        "start": begin,
    }, NO_PROCESSOR


async def get_mv_list_all(mid: str) -> list[dict[str, Any]]:
    """获取歌手所有专辑列表

    Args:
        mid: 歌手 mid
    """
    response = await get_mv_list(mid=mid, number=100, begin=0)

    total = response["total"]
    mvs = response["list"]
    if total <= 100:
        return cast(list[dict[str, Any]], mvs)

    rg = RequestGroup()
    for num in range(100, total, 100):
        rg.add_request(get_mv_list, mid=mid, number=100, begin=num)

    response = await rg.execute()
    for res in response:
        mvs.extend(res["list"])

    return mvs
