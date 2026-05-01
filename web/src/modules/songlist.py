"""歌单模块 Web 路由适配."""

from fastapi import HTTPException

from web.src.routing.route_types import RouteContext


def _song_info_tuples(song_ids: list[int], song_types: list[int]) -> list[tuple[int, int]]:
    """转换为 modules 层使用的显式歌曲元组."""
    if len(song_ids) != len(song_types):
        raise HTTPException(status_code=422, detail="song_id 与 song_type 数量必须一致")
    return list(zip(song_ids, song_types, strict=True))


async def _write_songlist_songs(context: RouteContext, method_name: str):
    """调用歌单歌曲写操作并返回业务数据."""
    method = getattr(context.client.songlist, method_name)
    return await method(
        dirid=context.params["dirid"],
        song_info=_song_info_tuples(context.params["song_id"], context.params["song_type"]),
        tid=context.params["tid"],
        credential=context.params["credential"],
    )


async def add_songs_adapter(context: RouteContext):
    """添加歌曲到歌单."""
    return await _write_songlist_songs(context, "add_songs")


async def del_songs_adapter(context: RouteContext):
    """删除歌单中的歌曲."""
    return await _write_songlist_songs(context, "del_songs")
