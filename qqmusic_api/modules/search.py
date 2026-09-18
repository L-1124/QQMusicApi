"""搜索相关 API."""

from enum import IntEnum
from typing import Any, Literal, overload

from ..core import ItemPaginatedCgiRequest, Platform
from ..core.endpoint import CgiRequestData, HttpRequestData, cgi_endpoint, http_endpoint
from ..core.pagination import MultiFieldContinuationStrategy, PageStrategy
from ..models.search import (
    AlbumSearch,
    CompleteResponse,
    GeneralSearchResponse,
    HotkeyResponse,
    MvSearch,
    QuickSearchResponse,
    SearchByTypeResponse,
    SearchSelector,
    SingerSearch,
    SongListSearch,
    SongSearch,
)
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
    + RINGTONE: 彩铃
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
    RINGTONE = 10
    AUDIO_ALBUM = 15
    AUDIO = 18


class SearchApi(ApiModule):
    """搜索相关 API."""

    @cgi_endpoint(
        key="search.get_hotkey",
        module="music.musicsearch.HotkeyService",
        method="GetHotkeyForQQMusicMobile",
        response_model=HotkeyResponse,
    )
    def get_hotkey(self) -> CgiRequestData:
        """获取热搜词列表.

        Returns:
            CgiRequest[HotkeyResponse]: 热搜词列表请求描述符.
        """
        return CgiRequestData(param={"search_id": get_searchID()})

    @cgi_endpoint(
        key="search.complete",
        module="music.smartboxCgi.SmartBoxCgi",
        method="GetSmartBoxResult",
        response_model=CompleteResponse,
    )
    def complete(self, keyword: str) -> CgiRequestData:
        """搜索词补全建议.

        Args:
            keyword: 关键词.

        Returns:
            CgiRequest[CompleteResponse]: 补全建议请求描述符.
        """
        return CgiRequestData(
            param={
                "search_id": get_searchID(),
                "query": keyword,
                "num_per_page": 0,
                "page_idx": 0,
            }
        )

    @http_endpoint(
        key="search.quick_search",
        method="GET",
        url="https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
        response_model=QuickSearchResponse,
    )
    def quick_search(self, keyword: str) -> HttpRequestData:
        """快速搜索.

        Args:
            keyword: 关键词.

        Returns:
            HttpRequest[QuickSearchResponse]: 快速搜索结果请求描述符.
        """
        return HttpRequestData(params={"key": keyword})

    @cgi_endpoint(
        key="search.general_search",
        module="music.adaptor.SearchAdaptor",
        method="do_search_v2",
        response_model=GeneralSearchResponse,
        pager=True,
    )
    def general_search(
        self,
        keyword: str,
        page: int = 1,
        num: int = 15,
        searchid: str | None = None,
        page_start: dict[str, Any] | None = None,
        *,
        highlight: bool = True,
    ) -> CgiRequestData:
        """综合搜索.

        Args:
            keyword: 关键词.
            page: 页码.
            num: 每页返回数量.
            searchid: 搜索会话 ID.
            page_start: 上一页分页游标对象.
            highlight: 是否高亮关键词.
        """
        param: dict[str, Any] = {
            "searchid": searchid or get_searchID(),
            "search_type": 100,
            "page_num": num,
            "query": keyword,
            "page_id": page,
            "highlight": highlight,
            "grp": True,
        }
        if page_start is not None:
            param["page_start"] = page_start

        return CgiRequestData(
            param=param,
            pager_strategy=MultiFieldContinuationStrategy[GeneralSearchResponse](
                lambda params, response: {
                    **params,
                    "searchid": response.searchid,
                    "page_id": response.nextpage,
                    "page_start": response.nextpage_start,
                },
                has_more_extractor=lambda response: response.nextpage != -1,
                context_name="general_search",
            ),
        )

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[
            SearchType.SONG, 0, SearchType.LYRIC, 7, SearchType.AUDIO, 18, SearchType.RINGTONE, 10
        ] = SearchType.SONG,
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, SongSearch]: ...

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[SearchType.SINGER, 1],
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, SingerSearch]: ...

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[SearchType.ALBUM, 2, SearchType.AUDIO_ALBUM, 15],
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, AlbumSearch]: ...

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[SearchType.SONGLIST, 3],
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, SongListSearch]: ...

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[SearchType.MV, 4],
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, MvSearch]: ...

    @overload
    def search_by_type(
        self,
        keyword: str,
        search_type: Literal[SearchType.USER, 8],
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> ItemPaginatedCgiRequest[SearchByTypeResponse, dict[str, Any]]: ...

    @cgi_endpoint(
        key="search.search_by_type",
        module="music.search.SearchCgiService",
        method="DoSearchForQQMusicMobile",
        platform=Platform.ANDROID,
        response_model=SearchByTypeResponse,
        pager=True,
    )
    def search_by_type(
        self,
        keyword: str,
        search_type: int | SearchType = SearchType.SONG,
        num: int = 10,
        page: int = 1,
        selectors: list[SearchSelector] | None = None,
        searchid: str | None = None,
        *,
        highlight: bool = True,
    ) -> CgiRequestData:
        """类型搜索.

        固定使用 Android 平台.

        Args:
            keyword: 关键词.
            search_type: 搜索类型.
            num: 返回结果数量.
            page: 页码.
            selectors: 搜索筛选器列表.
            searchid: 搜索会话 ID.
            highlight: 是否高亮关键词.
        """
        normalized_search_type = int(SearchType(search_type))

        def _extract_items(
            r: SearchByTypeResponse,
        ) -> (
            list[SongSearch]
            | list[SingerSearch]
            | list[AlbumSearch]
            | list[SongListSearch]
            | list[MvSearch]
            | list[dict[str, Any]]
        ):
            return r.song or r.singer or r.album or r.songlist or r.mv or r.user or r.audio_alum or []

        pager_strategy = PageStrategy[SearchByTypeResponse](
            page_key="page_num",
            page_size=num,
            start_page=page,
            has_more_extractor=lambda r: r.nextpage != -1,
            total_extractor=lambda r: r.total_num,
        )
        return CgiRequestData(
            param={
                "searchid": searchid or get_searchID(),
                "query": keyword,
                "search_type": normalized_search_type,
                "num_per_page": num,
                "page_num": page,
                "highlight": highlight,
                "grp": True,
                "selectors": {str(selector.type): str(selector.id) for selector in selectors} if selectors else {},
                "vec_selectors": [
                    {"type": selector.type, "name": selector.name, "id": selector.id} for selector in selectors
                ]
                if selectors
                else [],
            },
            pager_strategy=pager_strategy,
            items_extractor=_extract_items,
        )
