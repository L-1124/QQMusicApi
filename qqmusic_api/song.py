"""歌曲相关 API"""

from enum import Enum
from typing import Any, cast, overload

from .utils.common import get_guid
from .utils.credential import Credential
from .utils.network import NO_PROCESSOR, ApiRequest, RequestGroup, api_request


def _get_extract_func(key: str):
    def _func(data: dict[str, Any]) -> list[dict[str, Any]]:
        return data.get(key, [])

    return _func


@api_request("music.trackInfo.UniformRuleCtrl", "CgiGetTrackInfo")
async def query_song(value: list[int] | list[str]):
    """根据 id 或 mid 获取歌曲信息

    Args:
        value: 歌曲 id 或 mid 列表

    """
    params = {
        "types": [0 for _ in range(len(value))],
        "modify_stamp": [0 for _ in range(len(value))],
        "ctx": 0,
        "client": 1,
    }
    if isinstance(value[0], int):
        params["ids"] = value
    else:
        params["mids"] = value
    return params, lambda data: cast(list[dict[str, Any]], data["tracks"])


class BaseSongFileType(Enum):
    """基础歌曲文件类型"""

    def __init__(self, start_code: str, extension: str):
        self.__start_code = start_code
        self.__extension = extension

    @property
    def s(self) -> str:
        """歌曲文件类型"""
        return self.__start_code

    @property
    def e(self) -> str:
        """歌曲文件扩展名"""
        return self.__extension


class SongFileType(BaseSongFileType):
    """歌曲文件类型

    + MASTER: 臻品母带2.0,24Bit 192kHz,size_new[0]
    + ATMOS_2: 臻品全景声2.0,16Bit 44.1kHz,size_new[1]
    + ATMOS_51: 臻品音质2.0,16Bit 44.1kHz,size_new[2]
    + FLAC: flac 格式,16Bit 44.1kHz~24Bit 48kHz,size_flac
    + OGG_640: ogg 格式,640kbps,size_new[5]
    + OGG_320: ogg 格式,320kbps,size_new[3]
    + OGG_192: ogg 格式,192kbps,size_192ogg
    + OGG_96: ogg 格式,96kbps,size_96ogg
    + MP3_320: mp3 格式,320kbps,size_320mp3
    + MP3_128: mp3 格式,128kbps,size_128mp3
    + ACC_192: m4a 格式,192kbps,size_192aac
    + ACC_96: m4a 格式,96kbps,size_96aac
    + ACC_48: m4a 格式,48kbps,size_48aac
    """

    MASTER = ("AI00", ".flac")
    ATMOS_2 = ("Q000", ".flac")
    ATMOS_51 = ("Q001", ".flac")
    FLAC = ("F000", ".flac")
    OGG_640 = ("O801", ".ogg")
    OGG_320 = ("O800", ".ogg")
    OGG_192 = ("O600", ".ogg")
    OGG_96 = ("O400", ".ogg")
    MP3_320 = ("M800", ".mp3")
    MP3_128 = ("M500", ".mp3")
    ACC_192 = ("C600", ".m4a")
    ACC_96 = ("C400", ".m4a")
    ACC_48 = ("C200", ".m4a")


class EncryptedSongFileType(BaseSongFileType):
    """加密歌曲文件类型

    + MASTER: 臻品母带2.0,24Bit 192kHz,size_new[0]
    + ATMOS_2: 臻品全景声2.0,16Bit 44.1kHz,size_new[1]
    + ATMOS_51: 臻品音质2.0,16Bit 44.1kHz,size_new[2]
    + FLAC: mflac 格式,16Bit 44.1kHz~24Bit 48kHz,size_flac
    + OGG_640: mgg 格式,640kbps,size_new[5]
    + OGG_320: mgg 格式,320kbps,size_new[3]
    + OGG_192: mgg 格式,192kbps,size_192ogg
    + OGG_96: mgg 格式,96kbps,size_96ogg
    """

    MASTER = ("AIM0", ".mflac")
    ATMOS_2 = ("Q0M0", ".mflac")
    ATMOS_51 = ("Q0M1", ".mflac")
    FLAC = ("F0M0", ".mflac")
    OGG_640 = ("O801", ".mgg")
    OGG_320 = ("O800", ".mgg")
    OGG_192 = ("O6M0", ".mgg")
    OGG_96 = ("O4M0", ".mgg")


@overload
async def get_song_urls(
    mid: list[str],
    file_type: SongFileType = SongFileType.MP3_128,
    *,
    credential: Credential | None = None,
) -> dict[str, str]: ...


@overload
async def get_song_urls(
    mid: list[str],
    file_type: EncryptedSongFileType,
    *,
    credential: Credential | None = None,
) -> dict[str, tuple[str, str]]: ...


async def get_song_urls(
    mid: list[str],
    file_type: SongFileType | EncryptedSongFileType = SongFileType.MP3_128,
    *,
    credential: Credential | None = None,
) -> dict[str, str] | dict[str, tuple[str, str]]:
    """获取歌曲文件链接

    Tips:
        `ekey` 用于解密加密歌曲

    Args:
        mid: 歌曲 mid
        file_type: 歌曲文件类型
        credential: 账号凭证

    Returns:
        SongFileType: `{mid: url}`
        EncryptedSongFileType: `{mid: (url, ekey)}`
    """
    encrypted = isinstance(file_type, EncryptedSongFileType)
    # 分割 id,单次最大请求100
    mid_list = [mid[i : i + 100] for i in range(0, len(mid), 100)]
    # 选择文件域名
    domain = "https://isure.stream.qqmusic.qq.com/"
    api_data = ("music.vkey.GetVkey", "UrlGetVkey") if not encrypted else ("music.vkey.GetEVkey", "CgiGetEVkey")

    def _processor(res: dict[str, Any]):
        urls = {}
        data = res["midurlinfo"]
        for info in data:
            song_url = (
                domain + info.get("purl") or info.get("wifiurl") if info.get("purl") or info.get("wifiurl") else ""
            )
            if not encrypted:
                urls[info["songmid"]] = song_url
            else:
                urls[info["songmid"]] = (song_url, info["ekey"])
        return urls

    rg = RequestGroup(common={"ct": "19"}, credential=credential)
    for mid in mid_list:
        # 构造请求参数
        file_name = [f"{file_type.s}{_}{_}{file_type.e}" for _ in mid]
        params = {
            "filename": file_name,
            "guid": get_guid(),
            "songmid": mid,
            "songtype": [0 for _ in range(len(mid))],
        }
        req = ApiRequest(
            api_data[0],
            api_data[1],
            params=params,
            credential=credential,
        )
        req.processor = _processor
        rg.add_request(req)

    data = await rg.execute()
    result = {}
    for urls in data:
        result.update(urls)
    return result


@api_request("music.vkey.GetVkey", "UrlGetVkey")
async def get_try_url(mid: str, vs: str):
    """获取试听文件链接

    Tips:
        使用 `size_try` 字段判断是否存在试听文件
        参数 `vs` 请传入歌曲信息 `vs` 字段第一个

    Args:
        mid: 歌曲 mid
        vs:  歌曲 vs

    """
    return {
        "filename": [f"RS02{vs}.mp3"],
        "guid": get_guid(),
        "songmid": [mid],
        "songtype": [1],
    }, lambda res: f"https://isure.stream.qqmusic.qq.com/{url}" if (url := res["midurlinfo"][0]["wifiurl"]) else None


@api_request("music.pf_song_detail_svr", "get_song_detail_yqq")
async def get_detail(value: str | int):
    """获取歌曲详细信息

    Args:
        value: 歌曲 id 或 mid
    """
    if isinstance(value, int):
        return {"song_id": value}, NO_PROCESSOR
    return {"song_mid": value}, NO_PROCESSOR


@api_request("music.recommend.TrackRelationServer", "GetSimilarSongs")
async def get_similar_song(songid: int):
    """获取歌曲相似歌曲

    Args:
        songid: 歌曲 id
    """
    return {"songid": songid}, _get_extract_func("vecSong")


@api_request("music.recommend.TrackRelationServer", "GetSongLabels")
async def get_lables(songid: int):
    """获取歌曲标签

    Args:
        songid: 歌曲 id
    """
    return {"songid": songid}, _get_extract_func("labels")


@api_request("music.recommend.TrackRelationServer", "GetRelatedPlaylist")
async def get_related_songlist(songid: int):
    """获取歌曲相关歌单

    Args:
        songid: 歌曲 id
    """
    return {"songid": songid}, _get_extract_func("vecPlaylist")


@api_request("MvService.MvInfoProServer", "GetSongRelatedMv")
async def get_related_mv(songid: int, last_mvid: str | None = None):
    """获取相关 MV

    Args:
        songid: 歌曲 id
        last_mvid: 上次数据的最后的 MV 的 id
    """
    return {
        "songid": songid,
        "songtype": 1,
        **({"lastmvid": last_mvid} if last_mvid else {}),
    }, _get_extract_func("list")


@api_request("music.musichallSong.OtherVersionServer", "GetOtherVersionSongs")
async def get_other_version(value: str | int):
    """获取歌曲其他版本

    Args:
        value: 歌曲 id 或 mid
    """
    if isinstance(value, int):
        return {"songid": value}, _get_extract_func("versionList")
    return {"songmid": value}, _get_extract_func("versionList")


@api_request("music.sociality.KolWorksTag", "SongProducer")
async def get_producer(value: str | int):
    """获取歌曲制作者信息

    Args:
        value: 歌曲 id 或 mid
    """
    if isinstance(value, int):
        return {"songid": value}, _get_extract_func("Lst")
    return {"songmid": value}, _get_extract_func("Lst")


@api_request("music.mir.SheetMusicSvr", "GetMoreSheetMusic")
async def get_sheet(mid: str):
    """获取歌曲相关曲谱

    Args:
        mid: 歌曲 mid
    """
    return {"songmid": mid, "scoreType": -1}, _get_extract_func("result")


@api_request("music.musicasset.SongFavRead", "GetSongFansNumberById")
async def get_fav_num(songid: list[int]):
    """获取歌曲收藏数量

    Args:
        songid: 歌曲 id 列表
    """
    # 返回内容类似
    # {'m_numbers': {'438910555': 1000001}, 'm_show': {'438910555': '550w+'}}
    # 暂时选择 m_show 方便阅读
    return {"v_songId": songid}, _get_extract_func("m_show")
