"""歌单相关 API"""

from typing import Any, cast

from .utils.credential import Credential
from .utils.network import RequestGroup, api_request


@api_request("music.srfDissInfo.DissInfo", "CgiGetDiss")
async def get_detail(
    songlist_id: int,
    dirid: int = 0,
    num: int = 10,
    page: int = 1,
    onlysong: bool = False,
    tag: bool = True,
    userinfo: bool = True,
):
    """获取歌单详细信息和歌曲

    Args:
        songlist_id: 歌单 ID
        dirid: 歌单 dirid
        num: 返回数量
        page: 页码
        onlysong: 是否仅返回歌曲信息(优先级最大)
        tag: 是否返回歌单的标签信息
        userinfo: 是否返回歌单创建者的用户信息
    """

    def _processsor(data: dict[str, Any]):
        return {
            "dirinfo": data.get("dirinfo", {}),
            "total_song_num": data.get("total_song_num", 0),
            "songlist_size": data.get("songlist_size", 0),
            "songlist": data.get("songlist", []),
            "songtag": data.get("songtag", []),
            "orderlist": data.get("orderlist", []),
        }

    return {
        "disstid": songlist_id,
        "dirid": dirid,
        "tag": tag,
        "song_begin": num * (page - 1),
        "song_num": num,
        "userinfo": userinfo,
        "orderlist": True,
        "onlysonglist": onlysong,
    }, _processsor


async def get_songlist(
    songlist_id: int,
    dirid: int = 0,
) -> list[dict[str, Any]]:
    """获取歌单中所有歌曲列表

    Args:
        songlist_id: 歌单 ID
        dirid: 歌单 dirid
    """
    response = await get_detail(songlist_id=songlist_id, dirid=dirid, num=100, onlysong=True)

    total = response["total_song_num"]
    songs = response["songlist"]
    if total <= 100:
        return cast(list[dict[str, Any]], songs)

    rg = RequestGroup()
    for p, num in enumerate(range(100, total, 100), start=2):
        rg.add_request(get_detail, songlist_id=songlist_id, dirid=dirid, num=100, page=p, onlysong=True)

    response = await rg.execute()
    for res in response:
        songs.extend(res["songlist"])

    return songs


@api_request("music.musicasset.PlaylistBaseWrite", "AddPlaylist", verify=True)
async def create(dirname: str, *, credential: Credential | None = None):
    """创建歌单, 重名会在名称后面添加时间戳

    Args:
        dirname: 歌单名称
        credential: 凭证

    Returns:
        创建的歌单基本信息
    """
    return {
        "dirName": dirname,
    }, lambda data: cast(dict[str, Any], data["result"])


@api_request("music.musicasset.PlaylistBaseWrite", "DelPlaylist", verify=True)
async def delete(dirid: int, *, credential: Credential | None = None):
    """删除歌单

    Args:
        dirid: 歌单id
        credential: 凭证

    Returns:
        是否删除成功若不存在则返回False
    """
    return {
        "dirId": dirid,
    }, lambda data: data["result"]["dirId"] == dirid


@api_request("music.musicasset.PlaylistDetailWrite", "AddSonglist", verify=True)
async def add_songs(dirid: int = 1, song_ids: list[int] = [], *, credential: Credential | None = None):
    """添加歌曲到歌单

    Args:
        dirid: 歌单 dirid
        song_ids: 歌曲 ID 列表
        credential: 凭证

    Returns:
        是否添加成功, 歌曲已存在返回False
    """
    return {
        "dirId": dirid,
        "v_songInfo": [{"songType": 0, "songId": songid} for songid in song_ids],
    }, lambda data: bool(data["result"]["updateTime"])


@api_request("music.musicasset.PlaylistDetailWrite", "DelSonglist", verify=True)
async def del_songs(dirid: int = 1, song_ids: list[int] = [], *, credential: Credential | None = None):
    """删除歌单歌曲

    Args:
        dirid: 歌单 dirid
        song_ids: 歌曲 ID 列表
        credential: 凭证

    Returns:
        是否删除成功, 歌曲不存在返回False
    """
    return {
        "dirId": dirid,
        "v_songInfo": [{"songType": 0, "songId": songid} for songid in song_ids],
    }, lambda data: bool(data["result"]["updateTime"])
