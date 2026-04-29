"""歌单模块 Web 路由适配."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from qqmusic_api import Client, Credential
from web.auth import credential_for_request, credential_from_cookies
from web.response import ApiResponse, success_response
from web.schema import COOKIE_SECURITY_REQUIREMENT

router = APIRouter(prefix="/songlist", tags=["songlist"])
credential_dependency = Depends(credential_from_cookies)


def _song_info_tuples(song_ids: list[int], song_types: list[int]) -> list[tuple[int, int]]:
    """转换为 modules 层使用的显式歌曲元组."""
    if len(song_ids) != len(song_types):
        raise HTTPException(status_code=422, detail="song_id 与 song_type 数量必须一致")
    return list(zip(song_ids, song_types, strict=True))


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


@router.get(
    "/add_songs",
    summary="添加歌曲到歌单",
    description="添加歌曲到歌单.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def songlist_add_songs(
    request: Request,
    dirid: Annotated[int, Query(description="歌单目录 ID.")],
    song_id: Annotated[list[int], Query(description="歌曲 ID 列表.")],
    song_type: Annotated[list[int], Query(description="歌曲类型列表.")],
    tid: int = Query(default=0, description="歌单 TID."),
    credential: Credential = credential_dependency,
):
    """添加歌曲到歌单."""
    return await _write_songlist_songs(
        request,
        "add_songs",
        dirid=dirid,
        song_info=_song_info_tuples(song_id, song_type),
        tid=tid,
        credential=credential,
    )


@router.get(
    "/del_songs",
    summary="删除歌单中的歌曲",
    description="删除歌单中的歌曲.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def songlist_del_songs(
    request: Request,
    dirid: Annotated[int, Query(description="歌单目录 ID.")],
    song_id: Annotated[list[int], Query(description="歌曲 ID 列表.")],
    song_type: Annotated[list[int], Query(description="歌曲类型列表.")],
    tid: int = Query(default=0, description="歌单 TID."),
    credential: Credential = credential_dependency,
):
    """删除歌单中的歌曲."""
    return await _write_songlist_songs(
        request,
        "del_songs",
        dirid=dirid,
        song_info=_song_info_tuples(song_id, song_type),
        tid=tid,
        credential=credential,
    )
