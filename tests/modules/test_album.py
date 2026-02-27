"""专辑模块测试."""

import pytest

from qqmusic_api.models.album import AlbumSongResponse
from qqmusic_api.modules.album import AlbumApi


def test_get_cover(mock_client):
    """测试获取专辑封面链接."""
    api = AlbumApi(mock_client)
    url = api.get_cover("002RaSAs4XFas0")
    assert "002RaSAs4XFas0" in url
    assert "300x300" in url

    with pytest.raises(ValueError, match=r".*"):
        api.get_cover("002RaSAs4XFas0", size=100)  # type: ignore


@pytest.mark.anyio
async def test_get_detail(mock_client, make_request):
    """测试获取专辑详细信息."""
    api = AlbumApi(mock_client)

    # 测试通过 mid 获取
    await make_request(
        api.get_detail("002RaSAs4XFas0"),
        expected_module="music.musichallAlbum.AlbumInfoServer",
        expected_method="GetAlbumDetail",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["albumMId"] == "002RaSAs4XFas0"

    # 测试通过 id 获取
    await make_request(
        api.get_detail(12345),
        expected_module="music.musichallAlbum.AlbumInfoServer",
        expected_method="GetAlbumDetail",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["albumId"] == 12345


@pytest.mark.anyio
async def test_get_song(mock_client, make_request):
    """测试获取专辑歌曲."""
    api = AlbumApi(mock_client)

    # 模拟返回数据
    mock_client.execute.return_value = AlbumSongResponse(
        songList=[],
        totalNum=0,
    )

    # 测试通过 mid 获取
    await make_request(
        api.get_song("002RaSAs4XFas0", num=20, page=2),
        expected_module="music.musichallAlbum.AlbumSongList",
        expected_method="GetAlbumSongList",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["albumMid"] == "002RaSAs4XFas0"
    assert args[0].param["num"] == 20
    assert args[0].param["begin"] == 20

    # 测试通过 id 获取
    await make_request(
        api.get_song(12345),
        expected_module="music.musichallAlbum.AlbumSongList",
        expected_method="GetAlbumSongList",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["albumId"] == 12345


def test_client_album_property(mock_client):
    """测试 Client.album 属性."""
    assert isinstance(mock_client.album, AlbumApi)
