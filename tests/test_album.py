"""专辑模块测试."""

from typing import Literal

import pytest

from qqmusic_api import Client

CoverSize = Literal[150, 300, 500, 800] | None


async def test_get_detail_by_id(client: Client) -> None:
    """测试通过专辑 ID 获取专辑详情."""
    result = await client.album.get_detail(100)
    assert result is not None


@pytest.mark.parametrize(
    ("mid", "num", "page"),
    [
        ("001uKKpF1RuJSd", 30, 1),
        ("001gR6jO1L4MWq", 5, 1),
        ("0041WVfh2vtlJE", 10, 2),
    ],
)
async def test_get_song(client: Client, mid: str, num: int, page: int) -> None:
    """测试获取专辑歌曲列表."""
    result = await client.album.get_song(mid, num=num, page=page)
    assert result is not None
