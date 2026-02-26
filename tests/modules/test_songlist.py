"""歌单模块测试."""

import pytest

from qqmusic_api import Credential
from qqmusic_api.core.exceptions import NotLoginError
from qqmusic_api.modules.songlist import SonglistApi


@pytest.mark.anyio
async def test_get_detail(mock_client, make_request):
    """测试获取歌单详情请求."""
    api = SonglistApi(mock_client)

    await make_request(
        api.get_detail(123, dirid=10, num=20, page=2, onlysong=True, tag=False, userinfo=False),
        expected_module="music.srfDissInfo.DissInfo",
        expected_method="CgiGetDiss",
    )

    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["disstid"] == 123
    assert request.param["dirid"] == 10
    assert request.param["song_begin"] == 20
    assert request.param["song_num"] == 20
    assert request.param["onlysonglist"] is True
    assert request.param["tag"] is False
    assert request.param["userinfo"] is False


@pytest.mark.anyio
async def test_write_methods_with_valid_credential(mock_client, make_request):
    """测试写接口在有效凭证下可构建请求."""
    api = SonglistApi(mock_client)
    credential = Credential(musicid=10001, musickey="key")

    await make_request(
        api.create("test", credential=credential),
        expected_module="music.musicasset.PlaylistBaseWrite",
        expected_method="AddPlaylist",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].credential is credential

    await make_request(
        api.delete(1, credential=credential),
        expected_module="music.musicasset.PlaylistBaseWrite",
        expected_method="DelPlaylist",
    )

    await make_request(
        api.add_songs(1, [101, 102], credential=credential),
        expected_module="music.musicasset.PlaylistDetailWrite",
        expected_method="AddSonglist",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["v_songInfo"] == [{"songType": 0, "songId": 101}, {"songType": 0, "songId": 102}]

    await make_request(
        api.del_songs(1, [101], credential=credential),
        expected_module="music.musicasset.PlaylistDetailWrite",
        expected_method="DelSonglist",
    )


def test_write_methods_require_login(mock_client):
    """测试写接口无登录态时抛出异常."""
    api = SonglistApi(mock_client)

    with pytest.raises(NotLoginError):
        api.create("test")
    with pytest.raises(NotLoginError):
        api.delete(1)
    with pytest.raises(NotLoginError):
        api.add_songs(1, [1])
    with pytest.raises(NotLoginError):
        api.del_songs(1, [1])
