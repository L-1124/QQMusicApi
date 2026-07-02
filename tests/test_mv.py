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


async def test_get_mv_urls(client: Client) -> None:
    """测试获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_urls_multiple(client: Client) -> None:
    """测试批量获取 MV 播放链接."""
    result = await client.mv.get_mv_urls(["013xscuH0xlbie", "013xscuH0xlbie"])
    assert result is not None


async def test_get_mv_list(client: Client) -> None:
    """测试获取 MV 分类列表."""
    result = await client.mv.get_mv_list(area=15, version=7, order=0, num=5, page=1)
    assert result.total > 0
    assert result.items
    assert result.items[0].vid
    assert result.items[0].title


async def test_get_mv_list_pagination(client: Client) -> None:
    """测试 MV 分类列表分页返回不同数据."""
    pager = client.mv.get_mv_list(num=5, page=1).paginate(limit=2)
    first = await pager.next()
    second = await pager.next()
    assert first.items[0].vid != second.items[0].vid
