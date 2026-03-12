"""用户相关 API."""

from ..models.request import Credential
from ._base import ApiModule


class UserApi(ApiModule):
    """用户相关 API."""

    async def get_euin(self, musicid: int) -> str:
        """通过 musicid 获取 encrypt_uin (直接发起 HTTP 请求).

        Args:
            musicid: 用户数字 ID.

        Returns:
            str: 加密后的 UIN (encrypt_uin).
        """
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
        """通过 encrypt_uin 反查 musicid.

        Args:
            euin: 加密后的 UIN.
        """
        return self._build_request(
            module="music.srfDissInfo.DissInfo",
            method="CgiGetDiss",
            param={"disstid": 0, "dirid": 201, "song_num": 1, "enc_host_uin": euin, "onlysonglist": 1},
        )

    def get_homepage(self, euin: str, *, credential: Credential | None = None):
        """获取用户主页头部及统计信息.

        Args:
            euin: 加密后的 UIN.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"uin": euin, "IsQueryTabDetail": 1},
            credential=credential,
        )

    def get_vip_info(self, *, credential: Credential | None = None):
        """获取当前登录账号的 VIP 会员信息.

        Args:
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
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
        """获取用户关注的歌手列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
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
        """获取用户粉丝列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
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
        """获取好友列表.

        Args:
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
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
        """获取关注的用户列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
            module="music.concern.RelationList",
            method="GetFollowUserList",
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=target_credential,
        )

    def get_created_songlist(self, uin: str, *, credential: Credential | None = None):
        """获取用户创建的歌单列表.

        Args:
            uin: 用户 UIN.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
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
        """获取用户收藏的歌曲列表 (默认 dirid 为 201).

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 返回数量.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
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
        """获取用户收藏的外部歌单列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
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
        """获取用户收藏的专辑列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
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
        """获取用户收藏的 MV 列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
            module="music.musicasset.MVFavRead",
            method="getMyFavMV_v2",
            param={"encuin": euin, "pagesize": num, "num": page - 1},
            credential=target_credential,
        )

    def get_music_gene(self, euin: str, *, credential: Credential | None = None):
        """获取用户的音乐基因数据.

        Args:
            euin: 加密后的 UIN.
            credential: 登录凭证 (可选).
        """
        return self._build_request(
            module="music.recommend.UserProfileSettingSvr",
            method="GetProfileReport",
            param={"VisitAccount": euin},
            credential=credential,
        )
