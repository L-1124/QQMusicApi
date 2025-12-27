"""搜索相关 API"""

from enum import Enum
from typing import Any

from .utils.common import get_searchID
from .utils.network import NO_PROCESSOR, api_request
from .utils.session import get_session


class SearchType(Enum):
    """搜索类型

    + SONG: 歌曲
    + SINGER: 歌手
    + ALBUM: 专辑
    + SONGLIST: 歌单
    + MV: MV
    + LYRIC: 歌词
    + USER: 用户
    + AUDIO_SONG: 节目专辑
    + AUDIO: 节目
    """

    SONG = 0
    SINGER = 1
    ALBUM = 2
    SONGLIST = 3
    MV = 4
    LYRIC = 7
    USER = 8
    AUDIO_ALBUM = 15
    AUDIO = 18


@api_request("music.musicsearch.HotkeyService", "GetHotkeyForQQMusicMobile")
async def hotkey():
    """获取热搜词"""
    return {"search_id": get_searchID()}, NO_PROCESSOR


@api_request("music.smartboxCgi.SmartBoxCgi", "GetSmartBoxResult")
async def complete(keyword: str):
    """搜索词补全

    Args:
        keyword: 关键词
    """
    return {
        "search_id": get_searchID(),
        "query": keyword,
        "num_per_page": 0,
        "page_idx": 0,
    }, NO_PROCESSOR


async def quick_search(keyword: str) -> dict[str, Any]:
    """快速搜索

    Args:
        keyword: 关键词
    """
    resp = await get_session().get(
        "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
        params={
            "key": keyword,
        },
    )
    resp.raise_for_status()
    return resp.json()["data"]


@api_request("music.adaptor.SearchAdaptor", "do_search_v2")
async def general_search(
    keyword: str,
    page: int = 1,
    highlight: bool = True,
):
    """综合搜索

    Args:
        keyword: 关键词
        page: 页码
        highlight: 是否高亮关键词
    """
    return {
        "searchid": get_searchID(),
        "search_type": 100,
        "page_num": 15,
        "query": keyword,
        "page_id": page,
        "highlight": highlight,
        "grp": True,
    }, NO_PROCESSOR


@api_request("music.search.SearchCgiService", "DoSearchForQQMusicMobile")
async def search_by_type(
    keyword: str,
    search_type: SearchType = SearchType.SONG,
    num: int = 10,
    page: int = 1,
    highlight: bool = True,
):
    """搜索

    Args:
        keyword: 关键词
        search_type: 搜索类型
        num: 返回数量
        page: 页码
        highlight: 是否高亮关键词
    """
    params = {
        "searchid": get_searchID(),
        "query": keyword,
        "search_type": search_type.value,
        "num_per_page": num,
        "page_num": page,
        "highlight": highlight,
        "grp": True,
    }

    def _processor(data: dict[str, Any]) -> list[dict[str, Any]]:
        types = {
            SearchType.SONG: "item_song",
            SearchType.SINGER: "singer",
            SearchType.ALBUM: "item_album",
            SearchType.SONGLIST: "item_songlist",
            SearchType.MV: "item_mv",
            SearchType.LYRIC: "item_song",
            SearchType.USER: "item_user",
            SearchType.AUDIO_ALBUM: "item_audio",
            SearchType.AUDIO: "item_song",
        }
        return data["body"][types[search_type]]

    return params, _processor
