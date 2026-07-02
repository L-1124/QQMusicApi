"""专辑模块测试."""

from typing import Literal

import pytest

from qqmusic_api import Client, CredentialInvalidError

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


@pytest.mark.parametrize("area", [1, 2, 3])
async def test_get_new_album(client: Client, area: int) -> None:
    """测试按地区获取新碟上架列表."""
    result = await client.album.get_new_album(area=area, num=5, page=1)
    assert result.albums
    assert result.albums[0].mid
    assert result.albums[0].name


async def test_get_new_album_pagination(client: Client) -> None:
    """测试新碟上架分页返回不同数据."""
    pager = client.album.get_new_album(area=1, num=5, page=1).paginate(limit=2)
    first = await pager.next()
    second = await pager.next()
    assert first.albums[0].mid != second.albums[0].mid


async def test_fav_album_roundtrip(authenticated_client: Client) -> None:
    """测试收藏与取消收藏专辑可逆往返."""
    album = (await authenticated_client.album.get_new_album(area=1, num=1, page=1)).albums[0]
    assert (await authenticated_client.album.fav_album(album.id)).success
    assert (await authenticated_client.album.del_fav_album(album.id)).success


async def test_fav_album_requires_login(client: Client) -> None:
    """测试收藏专辑需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.album.fav_album(100)
