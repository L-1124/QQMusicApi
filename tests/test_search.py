"""搜索模块测试."""

import pytest

from qqmusic_api import Client
from qqmusic_api.modules.search import SearchType


async def test_get_hotkey(client: Client) -> None:
    """测试获取热搜词列表."""
    result = await client.search.get_hotkey()
    assert result


async def test_complete(client: Client) -> None:
    """测试搜索词补全建议."""
    result = await client.search.complete("周杰伦")
    assert result


async def test_quick_search(client: Client) -> None:
    """测试快速搜索."""
    result = await client.search.quick_search("周杰伦")
    assert result


@pytest.mark.parametrize("page", [1, 2])
async def test_general_search(client: Client, page: int) -> None:
    """测试综合搜索."""
    result = await client.search.general_search("周杰伦", page=page)
    assert result.song.items is not None
    assert result.related.items is not None


@pytest.mark.parametrize(
    ("search_type", "page", "num"),
    [
        (SearchType.SONG, 1, 10),
        (SearchType.SINGER, 1, 10),
        (SearchType.ALBUM, 1, 10),
        (SearchType.SONGLIST, 1, 10),
        (SearchType.MV, 1, 10),
        (SearchType.LYRIC, 1, 10),
        (SearchType.USER, 1, 10),
        (SearchType.AUDIO_ALBUM, 1, 10),
        (SearchType.AUDIO, 1, 10),
        (SearchType.SONG, 2, 5),
    ],
)
async def test_search_by_type(client: Client, search_type: SearchType, page: int, num: int) -> None:
    """测试按类型搜索."""
    result = await client.search.search_by_type("周杰伦", search_type=search_type, page=page, num=num)
    assert any((result.song, result.singer, result.album, result.songlist, result.user, result.audio_alum, result.mv))


async def test_search_by_type_with_int(client: Client) -> None:
    """测试按类型搜索支持整型枚举值."""
    result = await client.search.search_by_type("周杰伦", search_type=SearchType.SONG.value, page=1, num=5)
    assert result.song is not None


async def test_search_by_type_paginate(client: Client) -> None:
    """测试按类型搜索的分页能力."""
    # 测试分页迭代 (取前两页)
    pager = client.search.search_by_type("周杰伦", num=5, page=1).paginate()
    pages = []
    async for page in pager:
        pages.append(page)
        if len(pages) >= 2:
            break

    assert len(pages) == 2
    assert pages[0].nextpage == 2
