"""MV 模块 Web 路由适配."""

from web.src.routing.route_types import RouteContext


async def get_mv_urls_adapter(context: RouteContext):
    """批量获取 MV 播放链接."""
    return await context.client.mv.get_mv_urls(context.params["vids"])


async def get_mv_url_adapter(context: RouteContext):
    """获取单个 MV 播放链接."""
    return await context.client.mv.get_mv_urls([context.params["vid"]])
