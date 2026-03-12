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
async def test_get_cdn_dispatch_updates_domains(mock_client, monkeypatch):
    """测试内部 CDN 调度会更新域名缓存."""
    monkeypatch.setattr("qqmusic_api.modules.song.get_guid", lambda: "test-guid")
    monkeypatch.setattr("qqmusic_api.modules.song.time", lambda: 100.0)
    api = SongApi(mock_client)
    mock_client.execute.return_value = {
        "sip": ["http://ws6.stream.qqmusic.qq.com/", "https://aqqmusic.tc.qq.com/"],
        "sipinfo": [
            {
                "cdn": "http://ws6.stream.qqmusic.qq.com/",
                "quic": 0,
                "ipstack": 3,
                "quichost": "ws6.stream.qqmusic.qq.com",
                "plaintextquic": 0,
                "encryptquic": 0,
            },
            {
                "cdn": "https://aqqmusic.tc.qq.com/",
                "quic": 0,
                "ipstack": 1,
                "quichost": "aqqmusic.tc.qq.com",
                "plaintextquic": 0,
                "encryptquic": 0,
            },
        ],
        "refreshTime": 1800,
        "expiration": 86400,
        "cacheTime": 86400,
    }

    await api._get_cdn_dispatch(use_new_domain=False, use_ipv6=False)

    assert api._song_url_dispatch_data == {
        "sip": ["http://ws6.stream.qqmusic.qq.com/", "https://aqqmusic.tc.qq.com/"],
        "sipinfo": [
            {
                "cdn": "http://ws6.stream.qqmusic.qq.com/",
                "quic": 0,
                "ipstack": 3,
                "quichost": "ws6.stream.qqmusic.qq.com",
                "plaintextquic": 0,
                "encryptquic": 0,
            },
            {
                "cdn": "https://aqqmusic.tc.qq.com/",
                "quic": 0,
                "ipstack": 1,
                "quichost": "aqqmusic.tc.qq.com",
                "plaintextquic": 0,
                "encryptquic": 0,
            },
        ],
        "refreshTime": 1800,
        "expiration": 86400,
        "cacheTime": 86400,
    }
    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param == {
        "guid": "test-guid",
        "uid": "0",
        "use_new_domain": 0,
        "use_ipv6": 0,
    }
    assert api._SONG_URL_DOMAINS == ("http://ws6.stream.qqmusic.qq.com/", "https://aqqmusic.tc.qq.com/")
    assert api._song_url_domain_infos["https://aqqmusic.tc.qq.com/"]["ipstack"] == 1
    assert api._song_url_dispatch_refresh_at == 1900.0
    assert api._song_url_dispatch_expire_at == 86500.0


@pytest.mark.anyio
async def test_get_cdn_dispatch_uses_cache_before_refresh(mock_client, monkeypatch):
    """测试刷新时间前会直接复用缓存."""
    api = SongApi(mock_client)
    api._song_url_dispatch_data = {"sip": ["https://cached.qqmusic.qq.com/"]}
    api._song_url_dispatch_refresh_at = 200.0
    api._song_url_dispatch_expire_at = 300.0
    monkeypatch.setattr("qqmusic_api.modules.song.time", lambda: 150.0)

    await api._get_cdn_dispatch()

    assert api._song_url_dispatch_data == {"sip": ["https://cached.qqmusic.qq.com/"]}
    mock_client.execute.assert_not_called()


def test_choose_song_url_domain_randomly_chooses_domain(mock_client, monkeypatch):
    """测试歌曲下载域名会在当前候选中随机选择."""
    api = SongApi(mock_client)
    api._SONG_URL_DOMAINS = (
        "http://27.21.227.116/amobile.music.tc.qq.com/",
        "http://27.21.227.50/amobile.music.tc.qq.com/",
        "https://sjy6.stream.qqmusic.qq.com/",
    )
    captured: list[str] = []

    def _pick(options: list[str]) -> str:
        captured.extend(options)
        return options[-1]

    monkeypatch.setattr("qqmusic_api.modules.song.choice", _pick)

    assert api._choose_song_url_domain() == "https://sjy6.stream.qqmusic.qq.com/"
    assert captured == [
        "http://27.21.227.116/amobile.music.tc.qq.com/",
        "http://27.21.227.50/amobile.music.tc.qq.com/",
        "https://sjy6.stream.qqmusic.qq.com/",
    ]


@pytest.mark.anyio
async def test_get_song_urls_merges_batches(mock_client, monkeypatch):
    """测试批量歌曲链接会分批聚合返回."""
    api = SongApi(mock_client)
    monkeypatch.setattr("qqmusic_api.modules.song.choice", lambda options: options[-1])
    api._get_cdn_dispatch = AsyncMock(
        return_value={
            "sip": ["http://ws6.stream.qqmusic.qq.com/", "https://aqqmusic.tc.qq.com/"],
            "refreshTime": 1800,
            "expiration": 86400,
            "cacheTime": 86400,
        },
    )
    api._SONG_URL_DOMAINS = ("http://ws6.stream.qqmusic.qq.com/", "https://aqqmusic.tc.qq.com/")
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
        "mid-1": "https://aqqmusic.tc.qq.com/path-1",
        "mid-2": "https://aqqmusic.tc.qq.com/wifi-2",
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
    api._get_cdn_dispatch = AsyncMock(return_value={"sip": ["https://aqqmusic.tc.qq.com/"]})
    api._SONG_URL_DOMAINS = ("https://aqqmusic.tc.qq.com/",)
    group = Mock()
    group.add.return_value = group
    group.execute = AsyncMock(
        return_value=[{"midurlinfo": [{"songmid": "mid-1", "wifiurl": "wifi-1", "ekey": "key-1"}]}],
    )
    mock_client.request_group = Mock(return_value=group)

    result = await api.get_song_urls(["mid-1"], EncryptedSongFileType.FLAC)

    assert result == {"mid-1": ("https://aqqmusic.tc.qq.com/wifi-1", "key-1")}
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
    api._get_cdn_dispatch = AsyncMock(return_value={"sip": ["https://aqqmusic.tc.qq.com/"]})
    group = Mock()
    group.add.return_value = group
    group.execute = AsyncMock(return_value=[RuntimeError("boom")])
    mock_client.request_group = Mock(return_value=group)

    with pytest.raises(RuntimeError, match="boom"):
        await api.get_song_urls(["mid-1"])
