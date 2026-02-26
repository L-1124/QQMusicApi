"""推荐模块测试."""

import pytest

from qqmusic_api.modules.recommend import RecommendApi


@pytest.mark.anyio
async def test_get_home_feed(mock_client, make_request):
    """测试获取主页推荐."""
    api = RecommendApi(mock_client)
    await make_request(
        api.get_home_feed(),
        expected_module="music.recommend.RecommendFeed",
        expected_method="get_recommend_feed",
    )


@pytest.mark.anyio
async def test_get_guess_recommend(mock_client, make_request):
    """测试获取猜你喜欢."""
    api = RecommendApi(mock_client)
    await make_request(
        api.get_guess_recommend(),
        expected_module="music.radioProxy.MbTrackRadioSvr",
        expected_method="get_radio_track",
    )


@pytest.mark.anyio
async def test_get_radar_recommend(mock_client, make_request):
    """测试获取雷达推荐."""
    api = RecommendApi(mock_client)
    await make_request(
        api.get_radar_recommend(),
        expected_module="music.recommend.TrackRelationServer",
        expected_method="GetRadarSong",
    )


@pytest.mark.anyio
async def test_get_recommend_songlist(mock_client, make_request):
    """测试获取推荐歌单."""
    api = RecommendApi(mock_client)
    await make_request(
        api.get_recommend_songlist(),
        expected_module="music.playlist.PlaylistSquare",
        expected_method="GetRecommendFeed",
    )


@pytest.mark.anyio
async def test_get_recommend_newsong(mock_client, make_request):
    """测试获取推荐新歌."""
    api = RecommendApi(mock_client)
    await make_request(
        api.get_recommend_newsong(),
        expected_module="newsong.NewSongServer",
        expected_method="get_new_song_info",
    )


def test_client_recommend_property(mock_client):
    """测试 Client.recommend 属性."""
    assert isinstance(mock_client.recommend, RecommendApi)
