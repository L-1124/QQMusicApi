"""歌单模块 Web 路由适配."""

from fastapi import HTTPException

from qqmusic_api.modules.songlist import SonglistApi

from ..routing.adapter_registry import adapter
from ..routing.route_types import RouteContext


def _song_info_tuples(song_ids: list[int], song_types: list[int]) -> list[tuple[int, int]]:
    """转换为 modules 层使用的显式歌曲元组."""
    if len(song_ids) != len(song_types):
        raise HTTPException(status_code=422, detail="song_id 与 song_type 数量必须一致")
    return list(zip(song_ids, song_types, strict=True))


@adapter("songlist", "add_songs")
async def add_songs_adapter(context: RouteContext):
    """添加歌曲到歌单."""
    return await context.execute_endpoint(
        SonglistApi,
        SonglistApi.add_songs,
        dirid=context.params["dirid"],
        song_info=_song_info_tuples(context.params["song_id"], context.params["song_type"]),
        tid=context.params["tid"],
        credential=context.credential,
    )


@adapter("songlist", "del_songs")
async def del_songs_adapter(context: RouteContext):
    """删除歌单中的歌曲."""
    return await context.execute_endpoint(
        SonglistApi,
        SonglistApi.del_songs,
        dirid=context.params["dirid"],
        song_info=_song_info_tuples(context.params["song_id"], context.params["song_type"]),
        tid=context.params["tid"],
        credential=context.credential,
    )
