"""用户模块测试."""

import pytest

from qqmusic_api import Client
from qqmusic_api.models.user import UserFavMvResponse


async def test_get_homepage(client: Client) -> None:
    """测试未传凭证时主页接口自动补占位凭证."""
    result = await client.user.get_homepage(encrypt_uin="7eEFNeSlNKns")
    assert result.base_info.encrypt_uin


async def test_get_music_gene(client: Client) -> None:
    """测试获取用户音乐基因模型."""
    result = await client.user.get_music_gene(encrypt_uin="7eEFNeSlNKns")
    assert result.user_info_card.nick_name


async def test_relation_response_models_with_login(authenticated_client: Client) -> None:
    """测试关系接口返回可消费结果."""
    follow_singers = await authenticated_client.user.get_follow_singers(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
    )
    fans = await authenticated_client.user.get_fans(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
    )
    friends = await authenticated_client.user.get_friend()
    follow_users = await authenticated_client.user.get_follow_user(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
    )
    assert follow_singers.total >= 0
    assert fans.total >= 0
    assert friends.has_more in (True, False)
    assert follow_users.total >= 0


async def test_get_vip_info_with_login(authenticated_client: Client) -> None:
    """测试获取 VIP 信息模型."""
    result = await authenticated_client.user.get_vip_info()
    assert result.max_dir_num > 0
    assert result.max_song_num > 0
    assert result.userinfo.music_level >= 0
    assert result.svip >= 0
    assert result.star >= 0
    assert result.ystar >= 0
    assert result.identity.vip >= 0
    assert result.identity.huge_vip >= 0
    assert result.identity.year_flag >= 0
    assert result.identity.huge_year_flag >= 0
    assert result.identity.eight >= 0
    assert result.identity.level >= 0


async def test_get_created_songlist_with_login(authenticated_client: Client) -> None:
    """测试获取用户创建歌单列表模型."""
    result = await authenticated_client.user.get_created_songlist(
        uin=authenticated_client.credential.musicid,
        credential=authenticated_client.credential,
    )
    assert result.total >= 0
    assert result.finished in (True, False)
    assert result.playlists is not None


async def test_get_fav_song_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏歌曲列表模型."""
    result = await authenticated_client.user.get_fav_song(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= len(result.songs)
    assert result.info.id >= 0


async def test_get_fav_songlist_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏歌单列表模型."""
    result = await authenticated_client.user.get_fav_songlist(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= 0
    assert result.has_more in (0, 1)
    assert result.playlists is not None


async def test_get_fav_album_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏专辑列表模型."""
    result = await authenticated_client.user.get_fav_album(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.total >= 0
    assert result.has_more in (0, 1)
    assert result.albums is not None


async def test_get_fav_mv_with_login(authenticated_client: Client) -> None:
    """测试获取用户收藏 MV 列表模型."""
    result = await authenticated_client.user.get_fav_mv(
        encrypt_uin=authenticated_client.credential.encrypt_uin,
        credential=authenticated_client.credential,
        num=5,
        page=1,
    )
    assert result.code == 0
    assert result.subcode == 0
    assert result.mv_list is not None


@pytest.mark.parametrize("subcode_key", ["subCode", "subcode"])
def test_fav_mv_response_accepts_subcode_spellings(subcode_key: str) -> None:
    """测试收藏 MV 响应接受不同大小写的 subcode."""
    result = UserFavMvResponse.model_validate({"code": 0, subcode_key: 0, "msg": "", "mvlist": []})
    assert result.subcode == 0
