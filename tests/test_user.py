"""用户模块测试."""

from typing import Any

import pytest

from qqmusic_api import Client
from qqmusic_api.models.user import UserCreatedSonglistResponse, UserFavMvResponse

_PLAYLIST_PAYLOAD: dict[str, Any] = {
    "tid": 8000000000,
    "dirId": 201,
    "dirName": "我喜欢",
    "picUrl": "https://example.com/cover.jpg",
    "songNum": 3,
    "createTime": 1600000000,
    "updateTime": 1700000000,
    "uin": "10001",
    "nick": "tester",
    "bigpicUrl": "",
    "albumPicUrl": "",
    "avatar": "",
    "identIcon": "",
    "layerUrl": "",
    "invalid": 0,
    "dirShow": 1,
    "fav_cnt": 0,
    "play_cnt": 0,
    "comment_cnt": 0,
    "opType": 0,
    "sortWeight": 0,
}


async def test_get_homepage(client: Client) -> None:
    """测试未传凭证时主页接口自动补占位凭证."""
    result = await client.user.get_homepage(euin="7eEFNeSlNKns")
    assert result.base_info.encrypted_uin


async def test_get_music_gene(client: Client) -> None:
    """测试获取用户音乐基因模型."""
    result = await client.user.get_music_gene(euin="7eEFNeSlNKns")
    assert result.user_info_card.nick_name


async def test_relation_response_models_with_login(authenticated_client: Client) -> None:
    """测试关系接口返回可消费结果."""
    follow_singers = await authenticated_client.user.get_follow_singers(
        euin=authenticated_client.credential.encrypt_uin,
    )
    fans = await authenticated_client.user.get_fans(
        euin=authenticated_client.credential.encrypt_uin,
    )
    friends = await authenticated_client.user.get_friend()
    follow_users = await authenticated_client.user.get_follow_user(
        euin=authenticated_client.credential.encrypt_uin,
    )
    assert follow_singers.total >= 0
    assert fans.total >= 0
    assert friends.has_more in (True, False)
    assert follow_users.total >= 0


async def test_get_vip_info_with_login(authenticated_client: Client) -> None:
    """测试获取 VIP 信息模型."""
    result = await authenticated_client.user.get_vip_info()
    assert result.max_dir_num >= 0
    assert result.max_song_num >= 0
    assert result.userinfo.music_level >= 0


async def test_get_created_songlist_with_login(authenticated_client: Client) -> None:
    """测试获取用户创建歌单列表模型."""
    result = await authenticated_client.user.get_created_songlist(
        uin=authenticated_client.credential.musicid,
        credential=authenticated_client.credential,
    )
    assert result.total >= 0
    assert result.finished in (True, False)
    assert result.playlists is not None


@pytest.mark.parametrize(
    ("v_playlist", "expected_dirids"),
    [
        pytest.param(_PLAYLIST_PAYLOAD, [201], id="single-dict"),
        pytest.param([_PLAYLIST_PAYLOAD], [201], id="single-item-list"),
        pytest.param([_PLAYLIST_PAYLOAD, {**_PLAYLIST_PAYLOAD, "dirId": 202}], [201, 202], id="multi-item-list"),
    ],
)
def test_created_songlist_coerces_single_playlist(
    v_playlist: dict[str, Any] | list[dict[str, Any]],
    expected_dirids: list[int],
) -> None:
    """测试创建歌单响应兼容上游仅一个歌单时返回单对象的形态."""
    result = UserCreatedSonglistResponse.model_validate(
        {
            "total": len(expected_dirids),
            "v_playlist": v_playlist,
            "v_delTid": [],
            "bFinish": True,
        }
    )
    assert [playlist.dirid for playlist in result.playlists] == expected_dirids


async def test_get_fav_song_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏歌曲列表模型."""
    result = await authenticated_client.user.get_fav_song(
        euin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= len(result.songs)
    assert result.info.id >= 0


async def test_get_fav_songlist_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏歌单列表模型."""
    result = await authenticated_client.user.get_fav_songlist(
        euin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= 0
    assert result.hasmore in (0, 1)
    assert result.playlists is not None


async def test_get_fav_album_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏专辑列表模型."""
    result = await authenticated_client.user.get_fav_album(
        euin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= 0
    assert result.hasmore in (0, 1)
    assert result.albums is not None


async def test_get_fav_mv_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏 MV 列表模型."""
    result = await authenticated_client.user.get_fav_mv(
        euin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.code == 0
    assert result.sub_code == 0
    assert result.mv_list is not None


@pytest.mark.parametrize("sub_code_key", ["subCode", "subcode"])
def test_fav_mv_response_accepts_subcode_spellings(sub_code_key: str) -> None:
    """测试收藏 MV 响应兼容子返回码键名的两种大小写拼写."""
    result = UserFavMvResponse.model_validate({"code": 0, sub_code_key: 0, "msg": "", "mvlist": []})
    assert result.sub_code == 0
