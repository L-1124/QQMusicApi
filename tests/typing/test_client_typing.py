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

    detail_req = client.song.get_detail("0039MnYb0qxYAc")
    assert_type(detail_req, CgiRequest[GetSongDetailResponse])

    urls_req = client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")])
    assert_type(urls_req, CgiRequest[GetSongUrlsResponse])

    quick_req = client.search.quick_search("晴天")
    assert_type(quick_req, HttpRequest[QuickSearchResponse])

    # 验证 search_by_type 各重载的类型收窄与数据项提取推导
    song_req = client.search.search_by_type("晴天", search_type=SearchType.SONG)
    assert_type(song_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SongSearch])

    singer_req = client.search.search_by_type("周杰伦", search_type=SearchType.SINGER)
    assert_type(singer_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SingerSearch])

    album_req = client.search.search_by_type("魔杰座", search_type=SearchType.ALBUM)
    assert_type(album_req, ItemPaginatedCgiRequest[SearchByTypeResponse, AlbumSearch])

    songlist_req = client.search.search_by_type("流行", search_type=SearchType.SONGLIST)
    assert_type(songlist_req, ItemPaginatedCgiRequest[SearchByTypeResponse, SongListSearch])


async def _check_awaited_sdk_types(client: Client) -> None:
    """验证等待模块请求后可推导出精确响应类型."""
    assert_type(await client.song.get_detail("0039MnYb0qxYAc"), GetSongDetailResponse)
    assert_type(await client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")]), GetSongUrlsResponse)
    assert_type(await client.search.quick_search("晴天"), QuickSearchResponse)
