"""歌手模块 Web 路由适配."""

from web.src.routing.route_types import RouteContext


async def get_desc_by_mid_adapter(context: RouteContext):
    """根据单个歌手 MID 获取描述信息."""
    return await context.client.singer.get_desc([context.params["mid"]])
