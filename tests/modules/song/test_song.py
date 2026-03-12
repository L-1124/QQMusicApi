"""歌曲模块测试."""

from unittest.mock import AsyncMock, Mock

import pytest

from qqmusic_api.modules.song import EncryptedSongFileType, SongApi, SongFileType


def test_query_song_empty_raises(mock_client):
    """测试空列表查询会抛出异常."""
    api = SongApi(mock_client)
    with pytest.raises(ValueError, match=r".*"):
        api.query_song([])


@pytest.mark.anyio
async def test_query_song_with_mid(mock_client, make_request):
    """测试通过 mid 列表查询歌曲."""
    api = SongApi(mock_client)

    await make_request(
        api.query_song(["002mZevo3wHvsc"]),
        expected_module="music.trackInfo.UniformRuleCtrl",
        expected_method="CgiGetTrackInfo",
    )
    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["mids"] == ["002mZevo3wHvsc"]


@pytest.mark.anyio
async def test_query_song_with_id(mock_client, make_request):
    """测试通过 id 列表查询歌曲."""
    api = SongApi(mock_client)

    await make_request(
        api.query_song([12345]),
        expected_module="music.trackInfo.UniformRuleCtrl",
        expected_method="CgiGetTrackInfo",
    )
    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["ids"] == [12345]


@pytest.mark.anyio
async def test_song_methods(mock_client, make_request):
    """测试歌曲模块核心方法."""
    api = SongApi(mock_client)

    await make_request(
        api.get_try_url("002mZevo3wHvsc", "vS"),
        expected_module="music.vkey.GetVkey",
        expected_method="UrlGetVkey",
    )

    await make_request(
        api.get_detail(123),
        expected_module="music.pf_song_detail_svr",
        expected_method="get_song_detail_yqq",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param == {"song_id": 123}

    await make_request(
        api.get_detail("002mZevo3wHvsc"),
        expected_module="music.pf_song_detail_svr",
        expected_method="get_song_detail_yqq",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param == {"song_mid": "002mZevo3wHvsc"}

    await make_request(
        api.get_similar_song(123),
        expected_module="music.recommend.TrackRelationServer",
        expected_method="GetSimilarSongs",
    )
    await make_request(
        api.get_lables(123),
        expected_module="music.recommend.TrackRelationServer",
        expected_method="GetSongLabels",
    )
    await make_request(
        api.get_related_songlist(123),
        expected_module="music.recommend.TrackRelationServer",
        expected_method="GetRelatedPlaylist",
    )
    await make_request(
        api.get_related_mv(123, "v123"),
        expected_module="MvService.MvInfoProServer",
        expected_method="GetSongRelatedMv",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["lastmvid"] == "v123"

    await make_request(
        api.get_other_version("002mZevo3wHvsc"),
        expected_module="music.musichallSong.OtherVersionServer",
        expected_method="GetOtherVersionSongs",
    )
    await make_request(
        api.get_producer(123),
        expected_module="music.sociality.KolWorksTag",
        expected_method="SongProducer",
    )
    await make_request(
        api.get_sheet("002mZevo3wHvsc"),
        expected_module="music.mir.SheetMusicSvr",
        expected_method="GetMoreSheetMusic",
    )
    await make_request(
        api.get_fav_num([123]),
        expected_module="music.musicasset.SongFavRead",
        expected_method="GetSongFansNumberById",
    )


@pytest.mark.anyio
async def test_get_song_urls_merges_batches(mock_client):
    """测试批量歌曲链接会分批聚合返回."""
    api = SongApi(mock_client)
    group = Mock()
    group.add.return_value = group
    group.execute = AsyncMock(
        return_value=[
            {
                "midurlinfo": [
                    {"songmid": "mid-1", "purl": "path-1"},
                    {"songmid": "mid-2", "wifiurl": "wifi-2"},
                ],
            },
            {"midurlinfo": [{"songmid": "mid-101"}]},
        ],
    )
    mock_client.request_group = Mock(return_value=group)

    mids = [f"mid-{index}" for index in range(1, 102)]
    result = await api.get_song_urls(mids, SongFileType.MP3_128)

    assert result == {
        "mid-1": "https://isure.stream.qqmusic.qq.com/path-1",
        "mid-2": "https://isure.stream.qqmusic.qq.com/wifi-2",
        "mid-101": "",
    }
    mock_client.request_group.assert_called_once_with()
    assert group.add.call_count == 2
    first_request = group.add.call_args_list[0].args[0]
    second_request = group.add.call_args_list[1].args[0]
    assert first_request.module == "music.vkey.GetVkey"
    assert first_request.method == "UrlGetVkey"
    assert first_request.param["songmid"] == mids[:100]
    assert first_request.param["filename"][0] == "M500mid-1mid-1.mp3"
    assert second_request.param["songmid"] == mids[100:]


@pytest.mark.anyio
async def test_get_song_urls_supports_encrypted_type(mock_client):
    """测试加密歌曲链接会返回链接和 ekey."""
    api = SongApi(mock_client)
    group = Mock()
    group.add.return_value = group
    group.execute = AsyncMock(
        return_value=[{"midurlinfo": [{"songmid": "mid-1", "wifiurl": "wifi-1", "ekey": "key-1"}]}],
    )
    mock_client.request_group = Mock(return_value=group)

    result = await api.get_song_urls(["mid-1"], EncryptedSongFileType.FLAC)

    assert result == {"mid-1": ("https://isure.stream.qqmusic.qq.com/wifi-1", "key-1")}
    request = group.add.call_args.args[0]
    assert request.module == "music.vkey.GetEVkey"
    assert request.method == "CgiGetEVkey"
    assert request.param["filename"] == ["F0M0mid-1mid-1.mflac"]


@pytest.mark.anyio
async def test_get_song_urls_empty_input_returns_empty_dict(mock_client):
    """测试空 MID 列表直接返回空字典."""
    api = SongApi(mock_client)
    request_group = Mock()
    mock_client.request_group = request_group

    result = await api.get_song_urls([])

    assert result == {}
    request_group.assert_not_called()


@pytest.mark.anyio
async def test_get_song_urls_raises_batch_exception(mock_client):
    """测试批量请求异常会继续向外抛出."""
    api = SongApi(mock_client)
    group = Mock()
    group.add.return_value = group
    group.execute = AsyncMock(return_value=[RuntimeError("boom")])
    mock_client.request_group = Mock(return_value=group)

    with pytest.raises(RuntimeError, match="boom"):
        await api.get_song_urls(["mid-1"])
