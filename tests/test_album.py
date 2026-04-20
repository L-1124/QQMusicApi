"""专辑模块测试."""

from typing import Literal

import pytest

from qqmusic_api import Client

CoverSize = Literal[150, 300, 500, 800] | None


async def test_get_detail_by_id(client: Client) -> None:
    """测试通过专辑 ID 获取专辑详情."""
    result = await client.album.get_detail(100)
    assert result is not None


async def test_get_detail_by_mid(client: Client) -> None:
    """测试通过专辑 MID 获取专辑详情."""
    result = await client.album.get_detail("002fRO0N4FftzY")
    assert result is not None


@pytest.mark.parametrize(
    ("num", "page"),
    [
        (30, 1),
        (5, 1),
        (10, 2),
    ],
)
async def test_get_song(client: Client, num: int, page: int) -> None:
    """测试获取专辑歌曲列表."""
    result = await client.album.get_song(100, num=num, page=page)
    assert result is not None


async def test_get_song_by_mid(client: Client) -> None:
    """测试通过 MID 获取专辑歌曲列表."""
    result = await client.album.get_song("002fRO0N4FftzY", num=5)
    assert result is not None


async def test_get_song_pagination(client: Client) -> None:
    """测试专辑歌曲列表支持分页迭代."""
    pager = client.album.get_song(100, num=5, page=1).paginate(limit=2)
    assert pager.has_more() is True
    first = await pager.next()
    assert pager.has_more() is True
    second = await pager.next()
    assert first is not None
    assert second is not None
    assert pager.has_more() is False
    with pytest.raises(StopAsyncIteration):
        await pager.next()
