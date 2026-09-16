"""静态类型系统契约测试 (验证类型推导与泛型绑定无感兼容)."""

import pytest
from typing_extensions import assert_type

from qqmusic_api import Client
from qqmusic_api.core.request import CgiRequest, HttpRequest, ItemPaginatedCgiRequest
from qqmusic_api.models.search import (
    AlbumSearch,
    QuickSearchResponse,
    SearchByTypeResponse,
    SingerSearch,
    SongListSearch,
    SongSearch,
)
from qqmusic_api.models.song import (
    GetSongDetailResponse,
    GetSongUrlsResponse,
)
from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.song import SongFileInfo

pytestmark = pytest.mark.core


def test_client_facade_static_types():
    """验证 Client 门面方法向后兼容的原有强类型契约."""
    client = Client()

    # 1. 自动推断检查 (无显式变量注解)
    inferred_detail = client.song.get_detail("0039MnYb0qxYAc")
    assert_type(inferred_detail, CgiRequest[GetSongDetailResponse])

    inferred_urls = client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")])
    assert_type(inferred_urls, CgiRequest[GetSongUrlsResponse])

    inferred_quick = client.search.quick_search("晴天")
    assert_type(inferred_quick, HttpRequest[QuickSearchResponse])

    inferred_song = client.search.search_by_type("晴天", search_type=SearchType.SONG)
    assert_type(inferred_song, ItemPaginatedCgiRequest[SearchByTypeResponse, SongSearch])

    # 2. 显式契约赋值检查 (带目标类型注解)
    detail_req: CgiRequest[GetSongDetailResponse] = client.song.get_detail("0039MnYb0qxYAc")
    assert_type(detail_req, CgiRequest[GetSongDetailResponse])

    urls_req: CgiRequest[GetSongUrlsResponse] = client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")])
    assert_type(urls_req, CgiRequest[GetSongUrlsResponse])

    quick_req: HttpRequest[QuickSearchResponse] = client.search.quick_search("晴天")
    assert_type(quick_req, HttpRequest[QuickSearchResponse])

    song_req: ItemPaginatedCgiRequest[SearchByTypeResponse, SongSearch] = client.search.search_by_type(
        "晴天", search_type=SearchType.SONG
    )
    assert_type(song_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SongSearch])

    singer_req: ItemPaginatedCgiRequest[SearchByTypeResponse, SingerSearch] = client.search.search_by_type(
        "周杰伦", search_type=SearchType.SINGER
    )
    assert_type(singer_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SingerSearch])

    album_req: ItemPaginatedCgiRequest[SearchByTypeResponse, AlbumSearch] = client.search.search_by_type(
        "魔杰座", search_type=SearchType.ALBUM
    )
    assert_type(album_req, ItemPaginatedCgiRequest[SearchByTypeResponse, AlbumSearch])

    songlist_req: ItemPaginatedCgiRequest[SearchByTypeResponse, SongListSearch] = client.search.search_by_type(
        "流行", search_type=SearchType.SONGLIST
    )
    assert_type(songlist_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SongListSearch])


async def _check_awaited_sdk_types(client: Client) -> None:
    """验证等待模块请求后可推导出精确响应类型."""
    assert_type(await client.song.get_detail("0039MnYb0qxYAc"), GetSongDetailResponse)
    assert_type(await client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")]), GetSongUrlsResponse)
    assert_type(await client.search.quick_search("晴天"), QuickSearchResponse)
