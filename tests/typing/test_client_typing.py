"""Client 静态类型契约测试."""

import pytest
from typing_extensions import assert_type

from qqmusic_api import Client
from qqmusic_api.core.request import (
    CgiRequest,
    HttpRequest,
    ItemPaginatedCgiRequest,
    PaginatedCgiRequest,
)
from qqmusic_api.models.album import GetNewAlbumResponse, NewAlbumItem
from qqmusic_api.models.base import Song
from qqmusic_api.models.comment import CommentItem, CommentListResponse
from qqmusic_api.models.mv import GetMvListResponse, MvListItem
from qqmusic_api.models.recommend import RecommendFeedCardResponse, RecommendShelf
from qqmusic_api.models.search import (
    AlbumSearch,
    GeneralSearchResponse,
    QuickSearchResponse,
    SearchByTypeResponse,
    SingerSearch,
    SongListSearch,
    SongSearch,
)
from qqmusic_api.models.singer import HomepageTabDetailResponse
from qqmusic_api.models.song import (
    GetRelatedMvResponse,
    GetSongDetailResponse,
    GetSongUrlsResponse,
    RelatedMv,
)
from qqmusic_api.models.songlist import GetSonglistDetailResponse
from qqmusic_api.models.top import TopDetailResponse
from qqmusic_api.models.user import DislikeListData, RelationUser, UserRelationListResponse
from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.singer import TabType
from qqmusic_api.modules.song import SongFileInfo

pytestmark = pytest.mark.core


def test_client_facade_plain_types():
    """验证 Client 门面普通端点的静态类型推导."""
    client = Client()

    # 1. 自动推断检查 (无显式变量注解)
    inferred_detail = client.song.get_detail("0039MnYb0qxYAc")
    assert_type(inferred_detail, CgiRequest[GetSongDetailResponse])

    inferred_urls = client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")])
    assert_type(inferred_urls, CgiRequest[GetSongUrlsResponse])

    inferred_quick = client.search.quick_search("晴天")
    assert_type(inferred_quick, HttpRequest[QuickSearchResponse])

    # 2. 显式契约赋值检查 (带目标类型注解)
    detail_req: CgiRequest[GetSongDetailResponse] = client.song.get_detail("0039MnYb0qxYAc")
    assert_type(detail_req, CgiRequest[GetSongDetailResponse])

    urls_req: CgiRequest[GetSongUrlsResponse] = client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")])
    assert_type(urls_req, CgiRequest[GetSongUrlsResponse])

    quick_req: HttpRequest[QuickSearchResponse] = client.search.quick_search("晴天")
    assert_type(quick_req, HttpRequest[QuickSearchResponse])


def test_client_facade_item_paginated_types():
    """验证 Client 门面条目分页端点的条目类型推导."""
    client = Client()

    album_req = client.album.get_new_album(area=1, num=5, page=1)
    assert_type(album_req, ItemPaginatedCgiRequest[GetNewAlbumResponse, NewAlbumItem])

    album_annotated: ItemPaginatedCgiRequest[GetNewAlbumResponse, NewAlbumItem] = client.album.get_new_album(area=1)
    assert_type(album_annotated, ItemPaginatedCgiRequest[GetNewAlbumResponse, NewAlbumItem])

    mv_req = client.mv.get_mv_list(num=5, page=1)
    assert_type(mv_req, ItemPaginatedCgiRequest[GetMvListResponse, MvListItem])

    comment_req = client.comment.get_hot_comments(102065756, page_num=1, page_size=5)
    assert_type(comment_req, ItemPaginatedCgiRequest[CommentListResponse, CommentItem])

    relation_req = client.user.get_follow_singers("euin0000000000000000000000000000")
    assert_type(relation_req, ItemPaginatedCgiRequest[UserRelationListResponse, RelationUser])

    songlist_req = client.songlist.get_detail(songlist_id=7843129912, num=5, page=1)
    assert_type(songlist_req, ItemPaginatedCgiRequest[GetSonglistDetailResponse, Song])

    related_mv_req = client.song.get_related_mv(1114857)
    assert_type(related_mv_req, ItemPaginatedCgiRequest[GetRelatedMvResponse, RelatedMv])

    feed_req = client.recommend.get_home_feed()
    assert_type(feed_req, ItemPaginatedCgiRequest[RecommendFeedCardResponse, RecommendShelf])

    top_req = client.top.get_detail(26)
    assert_type(top_req, ItemPaginatedCgiRequest[TopDetailResponse, Song])


def test_client_facade_pure_paginated_types():
    """验证 Client 门面纯分页端点的响应类型推导."""
    client = Client()

    tab_req = client.singer.get_tab_detail("001BLpXF2DyJe2", TabType.SONG)
    assert_type(tab_req, PaginatedCgiRequest[HomepageTabDetailResponse])

    tab_annotated: PaginatedCgiRequest[HomepageTabDetailResponse] = client.singer.get_tab_detail(
        "001BLpXF2DyJe2", TabType.SONG
    )
    assert_type(tab_annotated, PaginatedCgiRequest[HomepageTabDetailResponse])

    general_req = client.search.general_search("周杰伦")
    assert_type(general_req, PaginatedCgiRequest[GeneralSearchResponse])

    dislike_req = client.user.get_dislike_list()
    assert_type(dislike_req, PaginatedCgiRequest[DislikeListData])


def test_client_facade_search_overload_types():
    """验证 Client 门面搜索端点多重重载的条目类型推导."""
    client = Client()

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


async def _check_awaited_client_types(client: Client) -> None:
    """验证等待门面请求与分页展开后的类型推导."""
    # 1. 普通请求 await 后直接获得响应模型实例
    assert_type(await client.song.get_detail("0039MnYb0qxYAc"), GetSongDetailResponse)
    assert_type(await client.song.get_song_urls([SongFileInfo(mid="0039MnYb0qxYAc")]), GetSongUrlsResponse)
    assert_type(await client.search.quick_search("晴天"), QuickSearchResponse)

    # 2. 批量并发请求按输入顺序推导出同质结果列表
    gathered = await client.gather(
        [
            client.song.get_detail("0039MnYb0qxYAc"),
            client.song.get_detail("004Z8Ihr0JIu5s"),
        ]
    )
    assert_type(gathered, list[GetSongDetailResponse])

    # 3. 重载搜索端点分别推导响应列表与条目列表
    paginated = client.search.search_by_type("晴天", search_type=SearchType.SONG)
    assert_type(await paginated.collect(), list[SearchByTypeResponse])
    assert_type(await paginated.collect_items(), list[SongSearch])

    # 4. 条目分页端点分别推导响应列表与条目列表
    item_paginated = client.album.get_new_album(area=1, num=5, page=1)
    assert_type(await item_paginated.collect(), list[GetNewAlbumResponse])
    assert_type(await item_paginated.collect_items(), list[NewAlbumItem])

    # 5. 纯分页端点仅支持响应列表推导
    pure_paginated = client.singer.get_tab_detail("001BLpXF2DyJe2", TabType.SONG)
    assert_type(await pure_paginated.collect(), list[HomepageTabDetailResponse])
