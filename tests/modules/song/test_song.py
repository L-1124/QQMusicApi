"""歌曲模块测试."""

import pytest

from qqmusic_api.modules.song import SongApi


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


def test_deleted_helper_not_present(mock_client):
    """测试被删除 helper 不存在."""
    api = SongApi(mock_client)
    assert not hasattr(api, "get_song_urls")
