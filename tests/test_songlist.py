"""歌单模块测试."""

import pytest

from qqmusic_api import Client, CredentialInvalidError


async def test_get_detail(client: Client) -> None:
    """测试获取歌单详细信息."""
    result = await client.songlist.get_detail(songlist_id=7843129912)
    assert result.info.id == 7843129912


async def test_get_detail_with_pagination(client: Client) -> None:
    """测试分页获取歌单歌曲列表."""
    result = await client.songlist.get_detail(songlist_id=7843129912, num=5, page=1)
    assert len(result.songs) == 5


async def test_get_detail_page2(client: Client) -> None:
    """测试获取歌单歌曲列表第二页."""
    result = await client.songlist.get_detail(songlist_id=7843129912, num=10, page=2)
    assert result.total >= len(result.songs)


async def test_get_detail_only_song(client: Client) -> None:
    """测试仅获取歌单歌曲列表."""
    result = await client.songlist.get_detail(songlist_id=7843129912, onlysong=True)
    assert result.songs


async def test_get_detail_without_tag(client: Client) -> None:
    """测试获取歌单详情时不返回标签信息."""
    result = await client.songlist.get_detail(songlist_id=7843129912, tag=False)
    assert result.info.title


async def test_get_detail_without_userinfo(client: Client) -> None:
    """测试获取歌单详情时不返回用户信息."""
    result = await client.songlist.get_detail(songlist_id=7843129912, userinfo=False)
    assert result.info.id == 7843129912


async def test_create_requires_login(client: Client) -> None:
    """测试创建歌单需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.create("pytest-songlist")


async def test_delete_requires_login(client: Client) -> None:
    """测试删除歌单需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.delete(1)


async def test_add_songs_requires_login(client: Client) -> None:
    """测试添加歌曲到歌单需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.add_songs(dirid=1, song_info=[(100, 0)])


async def test_del_songs_requires_login(client: Client) -> None:
    """测试删除歌单歌曲需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.del_songs(dirid=1, song_info=[(100, 0)])
