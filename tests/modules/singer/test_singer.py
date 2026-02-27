"""歌手模块测试."""

import pytest

from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType, SingerApi, TabType, validate_int_enum


def test_validate_int_enum() -> None:
    """测试枚举与整数校验."""
    assert validate_int_enum(AreaType.CHINA, AreaType) == 200
    assert validate_int_enum(-100, AreaType) == -100
    with pytest.raises(ValueError, match=r".*"):
        validate_int_enum(999, AreaType)


@pytest.mark.anyio
async def test_get_singer_list(mock_client, make_request):
    """测试获取歌手列表请求."""
    api = SingerApi(mock_client)

    await make_request(
        api.get_singer_list(area=AreaType.CHINA, sex=SexType.MALE, genre=GenreType.POP),
        expected_module="music.musichallSinger.SingerList",
        expected_method="GetSingerList",
    )

    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["area"] == AreaType.CHINA.value
    assert request.param["sex"] == SexType.MALE.value
    assert request.param["genre"] == GenreType.POP.value


@pytest.mark.anyio
async def test_get_singer_list_index(mock_client, make_request):
    """测试获取歌手索引列表请求."""
    api = SingerApi(mock_client)

    await make_request(
        api.get_singer_list_index(index=IndexType.A, sin=80, cur_page=2),
        expected_module="music.musichallSinger.SingerList",
        expected_method="GetSingerListIndex",
    )

    args, _ = mock_client.execute.call_args
    request = args[0]
    assert request.param["index"] == IndexType.A.value
    assert request.param["sin"] == 80
    assert request.param["cur_page"] == 2


@pytest.mark.anyio
async def test_other_singer_methods(mock_client, make_request):
    """测试歌手模块其他核心方法."""
    api = SingerApi(mock_client)

    await make_request(
        api.get_info("002J4UUk29y8BY"),
        expected_module="music.UnifiedHomepage.UnifiedHomepageSrv",
        expected_method="GetHomepageHeader",
    )

    await make_request(
        api.get_tab_detail("002J4UUk29y8BY", TabType.SONG, page=2, num=20),
        expected_module="music.UnifiedHomepage.UnifiedHomepageSrv",
        expected_method="GetHomepageTabDetail",
    )

    await make_request(
        api.get_desc(["002J4UUk29y8BY"]),
        expected_module="music.musichallSinger.SingerInfoInter",
        expected_method="GetSingerDetail",
    )

    await make_request(
        api.get_similar("002J4UUk29y8BY", number=5),
        expected_module="music.SimilarSingerSvr",
        expected_method="GetSimilarSingerList",
    )

    await make_request(
        api.get_songs_list("002J4UUk29y8BY", number=30, begin=60),
        expected_module="musichall.song_list_server",
        expected_method="GetSingerSongList",
    )

    await make_request(
        api.get_album_list("002J4UUk29y8BY", number=30, begin=30),
        expected_module="music.musichallAlbum.AlbumListServer",
        expected_method="GetAlbumList",
    )

    await make_request(
        api.get_mv_list("002J4UUk29y8BY", number=100, begin=100),
        expected_module="MvService.MvInfoProServer",
        expected_method="GetSingerMvList",
    )


def test_deleted_helpers_not_present(mock_client) -> None:
    """测试被删除 helper 不存在."""
    api = SingerApi(mock_client)
    assert not hasattr(api, "get_singer_list_index_all")
    assert not hasattr(api, "get_songs")
    assert not hasattr(api, "get_songs_list_all")
    assert not hasattr(api, "get_album_list_all")
    assert not hasattr(api, "get_mv_list_all")
