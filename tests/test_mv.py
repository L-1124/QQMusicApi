"""MV 模块测试."""

from qqmusic_api import Client


async def test_get_detail(client: Client) -> None:
    """测试获取 MV 详细信息."""
    result = await client.mv.get_detail(["013xscuH0xlbie"])
    assert result is not None


async def test_get_detail_multiple(client: Client) -> None:
    """测试批量获取 MV 详细信息."""
    result = await client.mv.get_detail(["013xscuH0xlbie", "013xscuH0xlbie"])
    assert result is not None


async def test_get_detail_returns_video_keyed_by_vid(client: Client) -> None:
    """测试 get_detail 返回以 VID 为键的视频详情映射."""
    result = await client.mv.get_detail(["013xscuH0xlbie"])
    assert "013xscuH0xlbie" in result.data
    mv = result.data["013xscuH0xlbie"]
    assert mv.vid == "013xscuH0xlbie"
    assert mv.name


async def test_get_mv_urls(client: Client) -> None:
    """测试获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_urls_multiple(client: Client) -> None:
    """测试批量获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie", "013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_urls_returns_url_set_keyed_by_vid(client: Client) -> None:
    """测试 get_mv_urls 返回以 VID 为键的播放地址集合."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie"])
    assert "013xscuH0xlbie" in result.data
    url_set = result.data["013xscuH0xlbie"]
    assert isinstance(url_set.mp4, list)
    assert isinstance(url_set.hls, list)
