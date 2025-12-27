"""用户相关 API

传入有效 credential 获取他人的信息会更完整但会留痕,且部分 API 不会验证
credential 是否有效,强制 credential 的 API 在 credential 失效时会报错

Credential 使用优先级:
传入的 Credential > Session 的 Credential
"""

from typing import Any, cast

from .utils.credential import Credential
from .utils.network import NO_PROCESSOR, api_request
from .utils.session import get_session


async def get_euin(musicid: int) -> str:
    """通过 musicid 获取 encrypt_uin"""
    resp = await get_session().get(
        "https://c6.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg",
        params={"ct": 20, "cv": 4747474, "cid": 205360838, "userid": musicid},
    )
    data = resp.json().get("data", {})
    return data.get("creator", {}).get("encrypt_uin", "")


@api_request("music.srfDissInfo.DissInfo", "CgiGetDiss")
async def get_musicid(euin: str):
    """通过 encrypt_uin 反查 musicid"""
    return {"disstid": 0, "dirid": 201, "song_num": 1, "enc_host_uin": euin, "onlysonglist": 1}, lambda data: int(
        data.get("dirinfo", {}).get("creator", {}).get("musicid", 0)
    )


@api_request("music.UnifiedHomepage.UnifiedHomepageSrv", "GetHomepageHeader")
async def get_homepage(euin: str, *, credential: Credential | None = None):
    """获取用户主页信息(包含音乐基因、歌单等)

    Args:
        euin: encrypt_uin
        credential: 凭证
    """
    return {"uin": euin, "IsQueryTabDetail": 1}, NO_PROCESSOR


@api_request("VipLogin.VipLoginInter", "vip_login_base", verify=True)
async def get_vip_info(*, credential: Credential | None = None):
    """获取当前登录账号的 VIP 信息(需要凭证)"""
    return {}, NO_PROCESSOR


@api_request("music.concern.RelationList", "GetFollowSingerList", verify=True)
async def get_follow_singers(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取关注歌手列表

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"HostUin": euin, "From": (page - 1) * num, "Size": num}, lambda data: {
        "total": data.get("Total", 0),
        "list": data.get("List", []),
    }


@api_request("music.concern.RelationList", "GetFansList", verify=True)
async def get_fans(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取粉丝列表

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"HostUin": euin, "From": (page - 1) * num, "Size": num}, lambda data: {
        "total": data.get("Total", 0),
        "list": data.get("List", []),
    }


@api_request("music.homepage.Friendship", "GetFriendList", verify=True)
async def get_friend(page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取好友列表

    Args:
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {
        "PageSize": num,
        "Page": page - 1,
    }, lambda data: {"total": len(data.get("Friends", [])), "list": data.get("Friends", [])}


@api_request("music.concern.RelationList", "GetFollowUserList", verify=True)
async def get_follow_user(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取关注用户列表

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"HostUin": euin, "From": (page - 1) * num, "Size": num}, lambda data: {
        "total": data.get("Total", 0),
        "list": data.get("List", []),
    }


@api_request("music.musicasset.PlaylistBaseRead", "GetPlaylistByUin")
async def get_created_songlist(uin: str, *, credential: Credential | None = None):
    """获取创建的歌单

    Args:
        uin: musicid
        credential: 凭证
    """
    return {"uin": uin}, lambda data: cast(list[dict[str, Any]], data.get("v_playlist", []))


@api_request("music.srfDissInfo.DissInfo", "CgiGetDiss")
async def get_fav_song(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取收藏歌曲

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
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
        "disstid": 0,
        "dirid": 201,
        "tag": True,
        "song_begin": num * (page - 1),
        "song_num": num,
        "userinfo": True,
        "orderlist": True,
        "enc_host_uin": euin,
    }, _processsor


@api_request("music.musicasset.PlaylistFavRead", "CgiGetPlaylistFavInfo")
async def get_fav_songlist(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取收藏歌单

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"uin": euin, "offset": (page - 1) * num, "size": num}, NO_PROCESSOR


@api_request("music.musicasset.AlbumFavRead", "CgiGetAlbumFavInfo")
async def get_fav_album(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取收藏专辑

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"euin": euin, "offset": (page - 1) * num, "size": num}, NO_PROCESSOR


@api_request("music.musicasset.MVFavRead", "getMyFavMV_v2", verify=True)
async def get_fav_mv(euin: str, page: int = 1, num: int = 10, *, credential: Credential | None = None):
    """获取收藏 MV

    Args:
        euin: encrypt_uin
        num: 返回数量
        page: 页码
        credential: 凭证
    """
    return {"encuin": euin, "pagesize": num, "num": page - 1}, NO_PROCESSOR


@api_request("music.recommend.UserProfileSettingSvr", "GetProfileReport")
async def get_music_gene(euin: str, *, credential: Credential | None = None):
    """获取音乐基因数据

    Args:
        euin: encrypt_uin
        credential: 凭证
    """
    return {"VisitAccount": euin}, NO_PROCESSOR
