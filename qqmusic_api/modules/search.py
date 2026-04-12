"""搜索相关 API."""

from enum import IntEnum
from typing import Any, cast

from ..core import Platform
from ..core.pagination import MultiFieldContinuationStrategy, PagerMeta, PageStrategy, ResponseAdapter
from ..models.search import GeneralSearchResponse, SearchByTypeResponse
from ..utils import get_searchID
from ._base import ApiModule


class SearchType(IntEnum):
    """搜索类型.

    + SONG: 歌曲
    + SINGER: 歌手
    + ALBUM: 专辑
    + SONGLIST: 歌单
    + MV: MV
    + LYRIC: 歌词
    + USER: 用户
    + AUDIO_ALBUM: 节目专辑
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


class SearchApi(ApiModule):
    """搜索相关 API."""

    def get_hotkey(self):
        """获取热搜词列表."""
        return self._build_request(
            "music.musicsearch.HotkeyService",
            "GetHotkeyForQQMusicMobile",
            {"search_id": get_searchID()},
        )

    def complete(self, keyword: str):
        """搜索词补全建议.

        Args:
            keyword: 关键词.
        """
        return self._build_request(
            "music.smartboxCgi.SmartBoxCgi",
            "GetSmartBoxResult",
            {
                "search_id": get_searchID(),
                "query": keyword,
                "num_per_page": 0,
                "page_idx": 0,
            },
        )

    async def quick_search(self, keyword: str) -> dict[str, Any]:
        """快速搜索 (直接返回解析后的 JSON 数据).

        Args:
            keyword: 关键词.

        Returns:
            dict[str, Any]: 搜索结果字典.
        """
        resp = await self._client.fetch(
            "GET",
            "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
            params={"key": keyword},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def general_search(
        self,
        keyword: str,
        page: int = 1,
        *,
        highlight: bool = True,
    ):
        """综合搜索.

        Args:
            keyword: 关键词.
            page: 页码.
            highlight: 是否高亮关键词.
        """
        return self._build_request(
            "music.adaptor.SearchAdaptor",
            "do_search_v2",
            {
                "searchid": get_searchID(),
                "search_type": 100,
                "page_num": 15,
                "query": keyword,
                "page_id": page,
                "highlight": highlight,
                "grp": True,
            },
            response_model=GeneralSearchResponse,
            pager_meta=PagerMeta(
                strategy=MultiFieldContinuationStrategy(
                    lambda params, response, adapter: {
                        **cast("dict[str, Any]", params),
                        "searchid": response.searchid,
                        "page_id": response.nextpage,
                        "page_start": cast("dict[str, Any]", adapter.get_cursor(response)),
                    },
                    context_name="general_search",
                ),
                adapter=ResponseAdapter(
                    has_more_flag=lambda response: response.nextpage != -1,
                    cursor="nextpage_start",
                ),
            ),
        )

    def search_by_type(
        self,
        keyword: str,
        search_type: int | SearchType = SearchType.SONG,
        num: int = 10,
        page: int = 1,
        *,
        highlight: bool = True,
    ):
        """按类型搜索结果.

        Args:
            keyword: 关键词.
            search_type: 搜索类型.
            num: 返回结果数量.
            page: 页码.
            highlight: 是否高亮关键词.
        """
        normalized_search_type = int(SearchType(search_type))
        return self._build_request(
            "music.search.SearchCgiService",
            "DoSearchForQQMusicMobile",
            {
                "searchid": get_searchID(),
                "query": keyword,
                "search_type": normalized_search_type,
                "num_per_page": num,
                "page_num": page,
                "highlight": highlight,
                "grp": True,
            },
            platform=Platform.ANDROID,
            response_model=SearchByTypeResponse,
            pager_meta=PagerMeta(
                strategy=PageStrategy(page_key="page_num", page_size=num, start_page=page),
                adapter=ResponseAdapter(
                    has_more_flag=lambda r: getattr(r, "nextpage", -1) != -1,
                    total="total_num",
                ),
            ),
        )
