"""用户相关 API."""

from typing import ClassVar

from ..core.pagination import OffsetStrategy, PagerMeta, PageStrategy, ResponseAdapter
from ..models.request import Credential
from ..models.songlist import GetSonglistDetailResponse
from ..models.user import (
    UserCreatedSonglistResponse,
    UserFavAlbumResponse,
    UserFavMvResponse,
    UserFavSonglistResponse,
    UserFriendListResponse,
    UserHomepageResponse,
    UserMusicGeneResponse,
    UserRelationListResponse,
    UserVipInfoResponse,
)
from ._base import ApiModule


class UserApi(ApiModule):
    """用户相关 API."""

    PLACEHOLDER_CREDENTIAL: ClassVar[Credential] = Credential.model_validate(
        {
            "musicid": 1,
            "str_musicid": "1",
            "musickey": "placeholder-musickey",
            "encryptUin": "00000000000000000000000000000000",
            "loginType": 1,
        },
    )

    def _resolve_placeholder_credential(self, credential: Credential | None = None) -> Credential:
        """在缺省凭证时自动补一个占位凭证."""
        if credential is not None:
            return credential
        current = self._client.credential
        if current.musicid and current.musickey:
            return current
        return self.PLACEHOLDER_CREDENTIAL

    def get_homepage(self, euin: str, *, credential: Credential | None = None):
        """获取用户主页头部及统计信息.

        Args:
            euin: 加密后的 UIN.
            credential: 可选的登录凭证；未传入时优先使用客户端当前凭证，
                若客户端凭证不可用则自动使用占位凭证.
        """
        target_credential = self._resolve_placeholder_credential(credential)
        return self._build_request(
            module="music.UnifiedHomepage.UnifiedHomepageSrv",
            method="GetHomepageHeader",
            param={"uin": euin, "IsQueryTabDetail": 1},
            credential=target_credential,
            response_model=UserHomepageResponse,
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
            response_model=UserVipInfoResponse,
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
            response_model=UserRelationListResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="From", page_size_key="Size"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    total="total",
                    count=lambda response: len(response.users),
                ),
            ),
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
            response_model=UserRelationListResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="From", page_size_key="Size"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    total="total",
                    count=lambda response: len(response.users),
                ),
            ),
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
            response_model=UserFriendListResponse,
            pager_meta=PagerMeta(
                strategy=PageStrategy(page_key="Page", page_size=num, start_page=page - 1),
                adapter=ResponseAdapter(has_more_flag="has_more"),
            ),
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
            response_model=UserRelationListResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="From", page_size_key="Size"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    total="total",
                    count=lambda response: len(response.users),
                ),
            ),
        )

    def get_created_songlist(self, uin: int, *, credential: Credential | None = None):
        """获取用户创建的歌单列表.

        Args:
            uin: 用户 UIN.
            credential: 登录凭证.
        """
        return self._build_request(
            module="music.musicasset.PlaylistBaseRead",
            method="GetPlaylistByUin",
            param={"uin": str(uin)},
            credential=credential,
            response_model=UserCreatedSonglistResponse,
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
            credential: 登录凭证.
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
            response_model=GetSonglistDetailResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="song_begin", page_size_key="song_num"),
                adapter=ResponseAdapter(
                    has_more_flag="hasmore",
                    total="total",
                    count=lambda response: len(response.songs),
                ),
            ),
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
            credential: 登录凭证.
        """
        return self._build_request(
            module="music.musicasset.PlaylistFavRead",
            method="CgiGetPlaylistFavInfo",
            param={"uin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
            response_model=UserFavSonglistResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="offset", page_size_key="size"),
                adapter=ResponseAdapter(
                    has_more_flag="hasmore",
                    total="total",
                    count=lambda response: len(response.playlists),
                ),
            ),
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
            credential: 登录凭证.
        """
        return self._build_request(
            module="music.musicasset.AlbumFavRead",
            method="CgiGetAlbumFavInfo",
            param={"euin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
            response_model=UserFavAlbumResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="offset", page_size_key="size"),
                adapter=ResponseAdapter(
                    has_more_flag="hasmore",
                    total="total",
                    count=lambda response: len(response.albums),
                ),
            ),
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
            response_model=UserFavMvResponse,
        )

    def get_music_gene(self, euin: str, *, credential: Credential | None = None):
        """获取用户的音乐基因数据.

        Args:
            euin: 加密后的 UIN.
            credential: 登录凭证.
        """
        return self._build_request(
            module="music.recommend.UserProfileSettingSvr",
            method="GetProfileReport",
            param={"VisitAccount": euin},
            credential=credential,
            response_model=UserMusicGeneResponse,
        )
