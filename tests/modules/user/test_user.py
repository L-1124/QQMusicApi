"""用户模块测试."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from qqmusic_api import Credential
from qqmusic_api.core.exceptions import NotLoginError
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.modules.user import UserApi


@pytest.mark.anyio
async def test_get_euin_uses_http_request(mock_client):
    """测试 get_euin 通过 HTTP 请求获取数据."""
    api = UserApi(mock_client)
    response = MagicMock()
    response.json.return_value = {"data": {"creator": {"encrypt_uin": "abc123"}}}
    mock_client.fetch = AsyncMock(return_value=response)

    result = await api.get_euin(10001)

    mock_client.fetch.assert_called_once()
    call_args, call_kwargs = mock_client.fetch.call_args
    assert call_args[0] == "GET"
    assert "fcg_get_profile_homepage.fcg" in call_args[1]
    assert call_kwargs["params"]["ct"] == DEFAULT_VERSION_POLICY.desktop.ct
    assert call_kwargs["params"]["cv"] == DEFAULT_VERSION_POLICY.desktop.cv
    assert call_kwargs["params"]["userid"] == 10001
    assert result == "abc123"


@pytest.mark.anyio
async def test_get_musicu_methods(mock_client, make_request):
    """测试用户模块普通接口请求参数."""
    api = UserApi(mock_client)

    await make_request(
        api.get_musicid("euin"),
        expected_module="music.srfDissInfo.DissInfo",
        expected_method="CgiGetDiss",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["enc_host_uin"] == "euin"

    await make_request(
        api.get_homepage("euin"),
        expected_module="music.UnifiedHomepage.UnifiedHomepageSrv",
        expected_method="GetHomepageHeader",
    )

    await make_request(
        api.get_created_songlist("10001"),
        expected_module="music.musicasset.PlaylistBaseRead",
        expected_method="GetPlaylistByUin",
    )

    await make_request(
        api.get_fav_song("euin", page=2, num=20),
        expected_module="music.srfDissInfo.DissInfo",
        expected_method="CgiGetDiss",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["song_begin"] == 20
    assert args[0].param["song_num"] == 20

    await make_request(
        api.get_fav_songlist("euin", page=3, num=10),
        expected_module="music.musicasset.PlaylistFavRead",
        expected_method="CgiGetPlaylistFavInfo",
    )

    await make_request(
        api.get_fav_album("euin", page=2, num=5),
        expected_module="music.musicasset.AlbumFavRead",
        expected_method="CgiGetAlbumFavInfo",
    )

    await make_request(
        api.get_music_gene("euin"),
        expected_module="music.recommend.UserProfileSettingSvr",
        expected_method="GetProfileReport",
    )


@pytest.mark.anyio
async def test_verify_methods_with_login(mock_client, make_request):
    """测试 verify 方法在登录态下可构建请求."""
    api = UserApi(mock_client)
    credential = Credential(musicid=10001, musickey="key")

    await make_request(
        api.get_vip_info(credential=credential),
        expected_module="VipLogin.VipLoginInter",
        expected_method="vip_login_base",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].credential is credential

    await make_request(
        api.get_follow_singers("euin", page=2, num=10, credential=credential),
        expected_module="music.concern.RelationList",
        expected_method="GetFollowSingerList",
    )

    await make_request(
        api.get_fans("euin", credential=credential),
        expected_module="music.concern.RelationList",
        expected_method="GetFansList",
    )

    await make_request(
        api.get_friend(page=2, num=5, credential=credential),
        expected_module="music.homepage.Friendship",
        expected_method="GetFriendList",
    )

    await make_request(
        api.get_follow_user("euin", credential=credential),
        expected_module="music.concern.RelationList",
        expected_method="GetFollowUserList",
    )

    await make_request(
        api.get_fav_mv("euin", credential=credential),
        expected_module="music.musicasset.MVFavRead",
        expected_method="getMyFavMV_v2",
    )


def test_verify_methods_require_login(mock_client):
    """测试 verify 方法在无登录态时抛出异常."""
    api = UserApi(mock_client)

    with pytest.raises(NotLoginError):
        api.get_vip_info()
    with pytest.raises(NotLoginError):
        api.get_follow_singers("euin")
    with pytest.raises(NotLoginError):
        api.get_fans("euin")
    with pytest.raises(NotLoginError):
        api.get_friend()
    with pytest.raises(NotLoginError):
        api.get_follow_user("euin")
    with pytest.raises(NotLoginError):
        api.get_fav_mv("euin")
