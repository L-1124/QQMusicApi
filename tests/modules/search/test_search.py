"""搜索模块测试."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from qqmusic_api.modules.search import SearchApi, SearchType


@pytest.mark.anyio
async def test_get_hotkey(mock_client, make_request):
    """测试获取热搜词."""
    api = SearchApi(mock_client)

    await make_request(
        api.get_hotkey(),
        expected_module="music.musicsearch.HotkeyService",
        expected_method="GetHotkeyForQQMusicMobile",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert "search_id" in request_obj.param


@pytest.mark.anyio
async def test_complete(mock_client, make_request):
    """测试搜索词补全."""
    api = SearchApi(mock_client)

    await make_request(
        api.complete("周杰伦"),
        expected_module="music.smartboxCgi.SmartBoxCgi",
        expected_method="GetSmartBoxResult",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["query"] == "周杰伦"
    assert "search_id" in request_obj.param


@pytest.mark.anyio
async def test_quick_search(mock_client):
    """测试快速搜索."""
    api = SearchApi(mock_client)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"song": [], "singer": []}}

    mock_client.fetch = AsyncMock(return_value=mock_response)

    result = await api.quick_search("周杰伦")

    mock_client.fetch.assert_called_once()
    call_args, call_kwargs = mock_client.fetch.call_args
    assert call_args[0] == "GET"
    assert "smartbox_new.fcg" in call_args[1]
    assert call_kwargs["params"]["key"] == "周杰伦"
    assert result == {"song": [], "singer": []}


@pytest.mark.anyio
async def test_general_search(mock_client, make_request):
    """测试综合搜索."""
    api = SearchApi(mock_client)

    await make_request(
        api.general_search("周杰伦", page=2, highlight=False),
        expected_module="music.adaptor.SearchAdaptor",
        expected_method="do_search_v2",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["query"] == "周杰伦"
    assert request_obj.param["page_id"] == 2
    assert request_obj.param["highlight"] is False
    assert request_obj.param["search_type"] == 100


@pytest.mark.anyio
async def test_search_by_type_default(mock_client, make_request):
    """测试按类型搜索(默认歌曲类型)."""
    api = SearchApi(mock_client)

    await make_request(
        api.search_by_type("周杰伦"),
        expected_module="music.search.SearchCgiService",
        expected_method="DoSearchForQQMusicMobile",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["query"] == "周杰伦"
    assert request_obj.param["search_type"] == SearchType.SONG.value
    assert request_obj.param["num_per_page"] == 10
    assert request_obj.param["page_num"] == 1


@pytest.mark.anyio
async def test_search_by_type_singer(mock_client, make_request):
    """测试按歌手类型搜索."""
    api = SearchApi(mock_client)

    await make_request(
        api.search_by_type("周杰伦", search_type=SearchType.SINGER, num=5, page=2),
        expected_module="music.search.SearchCgiService",
        expected_method="DoSearchForQQMusicMobile",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["search_type"] == SearchType.SINGER.value
    assert request_obj.param["num_per_page"] == 5
    assert request_obj.param["page_num"] == 2


def test_search_type_enum_values():
    """测试 SearchType 枚举值完整性."""
    assert SearchType.SONG.value == 0
    assert SearchType.SINGER.value == 1
    assert SearchType.ALBUM.value == 2
    assert SearchType.SONGLIST.value == 3
    assert SearchType.MV.value == 4
    assert SearchType.LYRIC.value == 7
    assert SearchType.USER.value == 8
    assert SearchType.AUDIO_ALBUM.value == 15
    assert SearchType.AUDIO.value == 18
