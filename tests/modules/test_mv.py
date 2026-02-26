"""MV 模块测试."""

import pytest

from qqmusic_api.modules.mv import MvApi


@pytest.mark.anyio
async def test_get_detail(mock_client, make_request):
    """测试获取 MV 详细信息."""
    api = MvApi(mock_client)

    await make_request(
        api.get_detail(["v0044o7v707"]),
        expected_module="video.VideoDataServer",
        expected_method="get_video_info_batch",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["vidlist"] == ["v0044o7v707"]
    assert "vid" in args[0].param["required"]


@pytest.mark.anyio
async def test_get_mv_urls(mock_client, make_request):
    """测试获取 MV 播放链接."""
    api = MvApi(mock_client)

    await make_request(
        api.get_mv_urls(["v0044o7v707"]),
        expected_module="music.stream.MvUrlProxy",
        expected_method="GetMvUrls",
    )
    args, _ = mock_client.execute.call_args
    assert args[0].param["vids"] == ["v0044o7v707"]
    assert "guid" in args[0].param


def test_client_mv_property(mock_client):
    """测试 Client.mv 属性."""
    assert isinstance(mock_client.mv, MvApi)
