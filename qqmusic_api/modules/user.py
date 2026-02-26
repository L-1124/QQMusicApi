"""用户相关 API。"""

from ..models import Credential
from ._base import ApiModule


class UserApi(ApiModule):
    """用户相关 API。"""

    async def get_euin(self, musicid: int) -> str:
        """通过 musicid 获取 encrypt_uin。"""
        params = self._build_query_common_params("desktop")
        params.update({"cid": 205360838, "userid": musicid})
        response = await self._request(
            "GET",
            "https://c6.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg",
            params=params,
        )
        data = response.json().get("data", {})
        return data.get("creator", {}).get("encrypt_uin", "")

    def get_musicid(self, euin: str):
        """通过 encrypt_uin 反查 musicid。"""
        return self.build_request(
            module="music.srfDissInfo.DissInfo",
            method="CgiGetDiss",
            param={"disstid": 0, "dirid": 201, "song_num": 1, "enc_host_uin": euin, "onlysonglist": 1},
        )

    def get_homepage(self, euin: str, *, credential: Credential | None = None):
        """获取用户主页信息。"""
        return self.build_request(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"uin": euin, "IsQueryTabDetail": 1},
            credential=credential,
        )

    def get_vip_info(self, *, credential: Credential | None = None):
        """获取当前登录账号的 VIP 信息。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="VipLogin.VipLoginInter",
            method="vip_login_base",
            param={},
            credential=target_credential,
        )

    def get_follow_singers(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取关注歌手列表。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.concern.RelationList",
            method="GetFollowSingerList",
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=target_credential,
        )

    def get_fans(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取粉丝列表。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.concern.RelationList",
            method="GetFansList",
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=target_credential,
        )

    def get_friend(
        self,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取好友列表。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.homepage.Friendship",
            method="GetFriendList",
            param={"PageSize": num, "Page": page - 1},
            credential=target_credential,
        )

    def get_follow_user(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取关注用户列表。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.concern.RelationList",
            method="GetFollowUserList",
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=target_credential,
        )

    def get_created_songlist(self, uin: str, *, credential: Credential | None = None):
        """获取创建的歌单。"""
        return self.build_request(
            module="music.musicasset.PlaylistBaseRead",
            method="GetPlaylistByUin",
            param={"uin": uin},
            credential=credential,
        )

    def get_fav_song(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取收藏歌曲。"""
        return self.build_request(
            module="music.srfDissInfo.DissInfo",
            method="CgiGetDiss",
            param={
                "disstid": 0,
                "dirid": 201,
                "tag": True,
                "song_begin": num * (page - 1),
                "song_num": num,
                "userinfo": True,
                "orderlist": True,
                "enc_host_uin": euin,
            },
            credential=credential,
        )

    def get_fav_songlist(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取收藏歌单。"""
        return self.build_request(
            module="music.musicasset.PlaylistFavRead",
            method="CgiGetPlaylistFavInfo",
            param={"uin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
        )

    def get_fav_album(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取收藏专辑。"""
        return self.build_request(
            module="music.musicasset.AlbumFavRead",
            method="CgiGetAlbumFavInfo",
            param={"euin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
        )

    def get_fav_mv(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ):
        """获取收藏 MV。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.musicasset.MVFavRead",
            method="getMyFavMV_v2",
            param={"encuin": euin, "pagesize": num, "num": page - 1},
            credential=target_credential,
        )

    def get_music_gene(self, euin: str, *, credential: Credential | None = None):
        """获取音乐基因数据。"""
        return self.build_request(
            module="music.recommend.UserProfileSettingSvr",
            method="GetProfileReport",
            param={"VisitAccount": euin},
            credential=credential,
        )
