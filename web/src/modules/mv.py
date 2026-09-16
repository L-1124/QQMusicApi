"""MV 模块 Web 路由适配."""

from qqmusic_api.modules.mv import MvApi

from ..routing.adapter_registry import adapter
from ..routing.route_types import RouteContext


@adapter("mv", "get_mv_urls")
async def get_mv_urls_adapter(context: RouteContext):
    """批量获取 MV 播放链接."""
    return await context.execute_endpoint(
        MvApi,
        MvApi.get_mv_urls,
        vids=context.params["vids"],
    )


@adapter("mv", "get_mv_url")
async def get_mv_url_adapter(context: RouteContext):
    """获取单个 MV 播放链接."""
    return await context.execute_endpoint(
        MvApi,
        MvApi.get_mv_urls,
        vids=[context.params["vid"]],
    )
