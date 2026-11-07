"""歌单模块测试."""

import pytest

from qqmusic_api import Client, CredentialInvalidError
from qqmusic_api.modules.songlist import _build_songlist_oper_param


@pytest.mark.core
@pytest.mark.parametrize(
    ("read_type", "write_type"),
    [(0, 0), (1, 0), (2, 1), (3, 1), (4, 1), (5, 5), (6, 1), (110, 1), (111, 111), (112, 112), (113, 113), (114, 1)],
)
def test_songlist_write_type_mapping(read_type: int, write_type: int) -> None:
    """测试读取类型转换为歌单写入类型, 保持歌曲 ID 不变."""
    param = _build_songlist_oper_param(dirid=2, song_info=[(100, read_type)], tid=123)
    assert param["v_songInfo"] == [{"songId": 100, "songType": write_type}]


async def test_get_detail(client: Client) -> None:
    """测试获取歌单详细信息."""
    result = await client.songlist.get_detail(songlist_id=7843129912)
    assert result.info.id == 7843129912


async def test_get_detail_with_pagination(client: Client) -> None:
    """测试分页获取歌单歌曲列表."""
    req = client.songlist.get_detail(songlist_id=7843129912, num=5, page=1)
    result = await req
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


async def test_reorder_songs_requires_login(client: Client) -> None:
    """测试重排歌单歌曲需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.reorder_songs(dirid=1, song_info=[(100, 1)])


async def test_like_song_requires_login(client: Client) -> None:
    """测试收藏歌曲到我喜欢需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.like_song([(100, 0)])


async def test_unlike_song_requires_login(client: Client) -> None:
    """测试从我喜欢移除歌曲需要登录凭证."""
    with pytest.raises(CredentialInvalidError):
        await client.songlist.unlike_song([(100, 0)])


async def test_like_song_roundtrip(authenticated_client: Client) -> None:
    """测试收藏与取消收藏歌曲可逆往返."""
    song = (await authenticated_client.recommend.get_recommend_newsong(type=1)).songs[0]
    assert await authenticated_client.songlist.like_song([(song.id, song.type)])
    assert await authenticated_client.songlist.unlike_song([(song.id, song.type)])


async def test_add_del_songs_roundtrip(authenticated_client: Client) -> None:
    """测试在临时歌单中添加与删除歌曲后读回结果一致."""
    songs = (await authenticated_client.recommend.get_recommend_newsong(type=1)).songs[:2]
    song_info = [(s.id, s.type) for s in songs]
    created = await authenticated_client.songlist.create("pytest-add-del")
    try:
        assert await authenticated_client.songlist.add_songs(created.dirid, song_info, tid=created.id)
        added = await authenticated_client.songlist.get_detail(created.id, dirid=created.dirid, num=10)
        assert {s.id for s in added.songs} == {s.id for s in songs}
        assert await authenticated_client.songlist.del_songs(created.dirid, song_info, tid=created.id)
        deleted = await authenticated_client.songlist.get_detail(created.id, dirid=created.dirid, num=10)
        assert deleted.total == 0
    finally:
        await authenticated_client.songlist.delete(created.dirid)


async def test_reorder_songs_roundtrip(authenticated_client: Client) -> None:
    """测试在临时歌单中倒序重排歌曲后读回顺序一致."""
    songs = (await authenticated_client.recommend.get_recommend_newsong(type=1)).songs[:4]
    created = await authenticated_client.songlist.create("pytest-reorder")
    try:
        assert await authenticated_client.songlist.add_songs(
            created.dirid, [(s.id, s.type) for s in songs], tid=created.id
        )
        before = (await authenticated_client.songlist.get_detail(created.id, dirid=created.dirid, num=10)).songs
        target = list(reversed(before))
        assert await authenticated_client.songlist.reorder_songs(
            created.dirid, [(s.id, s.type) for s in target], tid=created.id
        )
        after = (await authenticated_client.songlist.get_detail(created.id, dirid=created.dirid, num=10)).songs
        assert [s.id for s in after] == [s.id for s in target]
    finally:
        await authenticated_client.songlist.delete(created.dirid)
