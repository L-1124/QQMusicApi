"""歌单模块 Web 路由适配."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from qqmusic_api import Client, Credential
from web.auth import credential_for_request, credential_from_cookies
from web.response import ApiResponse, success_response
from web.schema import COOKIE_SECURITY_REQUIREMENT

router = APIRouter(prefix="/songlist", tags=["songlist"])
credential_dependency = Depends(credential_from_cookies)


class SonglistSongItem(BaseModel):
    """歌单歌曲写操作请求项."""

    song_id: int = Field(description="歌曲 ID.")
    song_type: int = Field(description="歌曲类型.")


class SonglistSongsRequest(BaseModel):
    """歌单歌曲写操作请求体."""

    dirid: int = Field(description="歌单目录 ID.")
    song_info: list[SonglistSongItem] = Field(description="歌曲信息列表.")
    tid: int = Field(default=0, description="歌单 TID.")


def _song_info_tuples(song_info: list[SonglistSongItem]) -> list[tuple[int, int]]:
    """转换为 modules 层使用的显式歌曲元组."""
    return [(item.song_id, item.song_type) for item in song_info]


async def _write_songlist_songs(
    request: Request,
    method_name: str,
    *,
    dirid: int,
    song_info: list[tuple[int, int]],
    tid: int,
    credential: Credential,
):
    """调用歌单歌曲写操作并返回标准响应."""
    client: Client = request.app.state.client
    method = getattr(client.songlist, method_name)
    return success_response(
        await method(
            dirid=dirid,
            song_info=song_info,
            tid=tid,
            credential=credential_for_request(client, credential),
        )
    )


@router.post(
    "/add_songs",
    summary="添加歌曲到歌单",
    description="添加歌曲到歌单.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def songlist_add_songs(
    request: Request,
    body: SonglistSongsRequest,
    credential: Credential = credential_dependency,
):
    """添加歌曲到歌单."""
    return await _write_songlist_songs(
        request,
        "add_songs",
        dirid=body.dirid,
        song_info=_song_info_tuples(body.song_info),
        tid=body.tid,
        credential=credential,
    )


@router.post(
    "/del_songs",
    summary="删除歌单中的歌曲",
    description="删除歌单中的歌曲.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def songlist_del_songs(
    request: Request,
    body: SonglistSongsRequest,
    credential: Credential = credential_dependency,
):
    """删除歌单中的歌曲."""
    return await _write_songlist_songs(
        request,
        "del_songs",
        dirid=body.dirid,
        song_info=_song_info_tuples(body.song_info),
        tid=body.tid,
        credential=credential,
    )
