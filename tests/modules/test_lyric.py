"""歌词模块测试."""

import pytest

from qqmusic_api.modules.lyric import LyricApi


@pytest.mark.anyio
async def test_get_lyric_by_mid(mock_client, make_request):
    """测试通过 mid 获取歌词请求."""
    api = LyricApi(mock_client)

    await make_request(
        api.get_lyric("002mZevo3wHvsc", qrc=True, trans=True),
        expected_module="music.musichallSong.PlayLyricInfo",
        expected_method="GetPlayLyricInfo",
    )

    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["songMid"] == "002mZevo3wHvsc"
    assert request.param["ct"] == mock_client._version_policy.get_profile(mock_client.platform).ct
    assert request.param["cv"] == mock_client._version_policy.get_profile(mock_client.platform).cv
    assert request.param["qrc"] is True
    assert request.param["trans"] is True


@pytest.mark.anyio
async def test_get_lyric_by_id(mock_client, make_request):
    """测试通过 id 获取歌词请求."""
    api = LyricApi(mock_client)

    await make_request(
        api.get_lyric(123456, roma=True),
        expected_module="music.musichallSong.PlayLyricInfo",
        expected_method="GetPlayLyricInfo",
    )

    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["songId"] == 123456
    assert request.param["roma"] is True
