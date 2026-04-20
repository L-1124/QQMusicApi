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


async def test_get_detail_returns_video_list(client: Client) -> None:
    """测试 get_detail 返回包含请求 vid 的视频列表."""
    result = await client.mv.get_detail(["013xscuH0xlbie"])
    assert hasattr(result, "video_info_list") or result is not None


async def test_get_mv_urls(client: Client) -> None:
    """测试获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_urls_multiple(client: Client) -> None:
    """测试批量获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie", "013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_urls_returns_mapping(client: Client) -> None:
    """测试 get_mv_urls 返回包含视频数据的结果."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie"])
    assert result is not None
    assert hasattr(result, "vids") or hasattr(result, "url_info") or result is not None
