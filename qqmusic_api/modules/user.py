"""用户相关 API."""

from typing import Any, ClassVar

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import MultiFieldContinuationStrategy, OffsetStrategy, PageStrategy
from ..models.base import Song
from ..models.request import Credential
from ..models.songlist import GetSonglistDetailResponse
from ..models.user import (
    DislikeListData,
    FriendEntry,
    RelationUser,
    UserCreatedSonglistResponse,
    UserFavAlbumItem,
    UserFavAlbumResponse,
    UserFavMvResponse,
    UserFavSonglistItem,
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
        current = self._executor.credential
        if current.musicid and current.musickey:
            return current
        return self.PLACEHOLDER_CREDENTIAL

    @cgi_endpoint(
        key="user.get_homepage",
        module="music.UnifiedHomepage.UnifiedHomepageSrv",
        method="GetHomepageHeader",
        response_model=UserHomepageResponse,
    )
    def get_homepage(self, euin: str, *, credential: Credential | None = None) -> CgiRequestData:
        """获取用户主页头部及统计信息.

        Args:
            euin: 加密后的 UIN.
            credential: 可选的登录凭证; 未传入时优先使用客户端当前凭证,
                若客户端凭证不可用则自动使用占位凭证.
        """
        target_credential = self._resolve_placeholder_credential(credential)
        return CgiRequestData(
            param={"uin": euin, "IsQueryTabDetail": 1},
            credential=target_credential,
        )

    @cgi_endpoint(
        key="user.get_vip_info",
        module="VipLogin.VipLoginInter",
        method="vip_login_base",
        response_model=UserVipInfoResponse,
        require_login=True,
    )
    def get_vip_info(self, *, credential: Credential | None = None) -> CgiRequestData:
        """获取当前登录账号的 VIP 会员信息.

        Args:
            credential: 登录凭证.
        """
        return CgiRequestData(credential=credential)

    @cgi_endpoint(
        key="user.get_follow_singers",
        module="music.concern.RelationList",
        method="GetFollowSingerList",
        response_model=UserRelationListResponse,
        require_login=True,
        item_type=RelationUser,
    )
    def get_follow_singers(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户关注的歌手列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=credential,
            pager_strategy=OffsetStrategy[UserRelationListResponse](
                offset_key="From",
                page_size_key="Size",
                has_more_extractor=lambda r: r.has_more,
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.users),
            ),
            items_extractor=lambda r: r.users,
        )

    @cgi_endpoint(
        key="user.get_fans",
        module="music.concern.RelationList",
        method="GetFansList",
        response_model=UserRelationListResponse,
        require_login=True,
        item_type=RelationUser,
    )
    def get_fans(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户粉丝列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=credential,
            pager_strategy=OffsetStrategy[UserRelationListResponse](
                offset_key="From",
                page_size_key="Size",
                has_more_extractor=lambda r: r.has_more,
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.users),
            ),
            items_extractor=lambda r: r.users,
        )

    @cgi_endpoint(
        key="user.get_friend",
        module="music.homepage.Friendship",
        method="GetFriendList",
        response_model=UserFriendListResponse,
        require_login=True,
        item_type=FriendEntry,
    )
    def get_friend(
        self,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取好友列表.

        Args:
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"PageSize": num, "Page": page - 1},
            credential=credential,
            pager_strategy=PageStrategy[UserFriendListResponse](
                page_key="Page",
                page_size=num,
                start_page=page - 1,
                has_more_extractor=lambda r: r.has_more,
            ),
            items_extractor=lambda r: r.friends,
        )

    @cgi_endpoint(
        key="user.get_follow_user",
        module="music.concern.RelationList",
        method="GetFollowUserList",
        response_model=UserRelationListResponse,
        require_login=True,
        item_type=RelationUser,
    )
    def get_follow_user(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取关注的用户列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页返回数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"HostUin": euin, "From": (page - 1) * num, "Size": num},
            credential=credential,
            pager_strategy=OffsetStrategy[UserRelationListResponse](
                offset_key="From",
                page_size_key="Size",
                has_more_extractor=lambda r: r.has_more,
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.users),
            ),
            items_extractor=lambda r: r.users,
        )

    @cgi_endpoint(
        key="user.get_created_songlist",
        module="music.musicasset.PlaylistBaseRead",
        method="GetPlaylistByUin",
        response_model=UserCreatedSonglistResponse,
    )
    def get_created_songlist(
        self,
        uin: int,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户创建的歌单列表.

        Args:
            uin: 用户 UIN.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"uin": str(uin)},
            credential=credential,
        )

    @cgi_endpoint(
        key="user.get_fav_song",
        module="music.srfDissInfo.DissInfo",
        method="CgiGetDiss",
        response_model=GetSonglistDetailResponse,
        item_type=Song,
    )
    def get_fav_song(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户收藏的歌曲列表 (默认 dirid 为 201).

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 返回数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
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
            pager_strategy=OffsetStrategy[GetSonglistDetailResponse](
                offset_key="song_begin",
                page_size_key="song_num",
                has_more_extractor=lambda r: bool(r.hasmore),
                total_extractor=lambda r: r.total,
                count_extractor=lambda response: len(response.songs),
            ),
            items_extractor=lambda r: r.songs,
        )

    @cgi_endpoint(
        key="user.get_fav_songlist",
        module="music.musicasset.PlaylistFavRead",
        method="CgiGetPlaylistFavInfo",
        response_model=UserFavSonglistResponse,
        item_type=UserFavSonglistItem,
    )
    def get_fav_songlist(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户收藏的外部歌单列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"uin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
            pager_strategy=OffsetStrategy[UserFavSonglistResponse](
                offset_key="offset",
                page_size_key="size",
                has_more_extractor=lambda r: bool(r.hasmore),
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.playlists),
            ),
            items_extractor=lambda r: r.playlists,
        )

    async def fav_songlist(self, songlist_id: int, *, credential: Credential | None = None) -> bool:
        """收藏歌单 (将他人的公开歌单加入当前账号的收藏).

        Args:
            songlist_id: 歌单 ID, 即歌单的 disstid/pid (不是自建歌单的 dirid).
            credential: 登录凭证.

        Returns:
            是否收藏成功 (歌单已在收藏中也返回 True).
        """
        data = await self._build_cgi(
            module="music.musicasset.PlaylistFavWrite",
            method="FavPlaylist",
            param={"uin": (credential or self._executor.credential).encrypt_uin, "v_playlistId": [songlist_id]},
            credential=credential,
            require_login=True,
        )
        return data.get("result") == 0 and songlist_id not in (data.get("v_failedPlaylistId") or [])

    async def unfav_songlist(self, songlist_id: int, *, credential: Credential | None = None) -> bool:
        """取消收藏歌单.

        Args:
            songlist_id: 歌单 ID, 即歌单的 disstid/pid (不是自建歌单的 dirid).
            credential: 登录凭证.

        Returns:
            是否取消成功 (歌单本就不在收藏中也返回 True).
        """
        data = await self._build_cgi(
            module="music.musicasset.PlaylistFavWrite",
            method="CancelFavPlaylist",
            param={"uin": (credential or self._executor.credential).encrypt_uin, "v_playlistId": [songlist_id]},
            credential=credential,
            require_login=True,
        )
        return data.get("result") == 0 and songlist_id not in (data.get("v_failedPlaylistId") or [])

    @cgi_endpoint(
        key="user.get_fav_album",
        module="music.musicasset.AlbumFavRead",
        method="CgiGetAlbumFavInfo",
        response_model=UserFavAlbumResponse,
        item_type=UserFavAlbumItem,
    )
    def get_fav_album(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户收藏的专辑列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"euin": euin, "offset": (page - 1) * num, "size": num},
            credential=credential,
            pager_strategy=OffsetStrategy[UserFavAlbumResponse](
                offset_key="offset",
                page_size_key="size",
                has_more_extractor=lambda r: bool(r.hasmore),
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.albums),
            ),
            items_extractor=lambda r: r.albums,
        )

    @cgi_endpoint(
        key="user.get_fav_mv",
        module="music.musicasset.MVFavRead",
        method="getMyFavMV_v2",
        response_model=UserFavMvResponse,
        require_login=True,
    )
    def get_fav_mv(
        self,
        euin: str,
        page: int = 1,
        num: int = 10,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户收藏的 MV 列表.

        Args:
            euin: 加密后的 UIN.
            page: 页码.
            num: 每页数量.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"encuin": euin, "pagesize": num, "num": page - 1},
            credential=credential,
        )

    @cgi_endpoint(
        key="user.get_music_gene",
        module="music.recommend.UserProfileSettingSvr",
        method="GetProfileReport",
        response_model=UserMusicGeneResponse,
    )
    def get_music_gene(self, euin: str, *, credential: Credential | None = None) -> CgiRequestData:
        """获取用户的音乐基因数据.

        Args:
            euin: 加密后的 UIN.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"VisitAccount": euin},
            credential=credential,
        )

    @cgi_endpoint(
        key="user.get_dislike_list",
        module="music.feedback.FeedbackBlack",
        method="GetDislikeList",
        response_model=DislikeListData,
        sign=True,
        require_login=True,
        pager=True,
    )
    def get_dislike_list(
        self,
        cmd: int = 3,
        page: int = 1,
        lastid: int = 0,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取用户不喜欢列表.

        Args:
            cmd:    类型, 2=歌手 / 3=歌曲 / 4=风格.
            page:   页码.
            lastid: 分页游标.
            credential: 登录凭证.
        """
        lastid_fields = {2: "SingersLastid", 3: "SongLastid", 4: "StyleLastid"}
        param: dict[str, Any] = {"Cmd": cmd, "Page": page}
        if lastid:
            param[lastid_fields[cmd]] = lastid

        def _build_next_params(p: dict[str, Any], r: DislikeListData) -> dict[str, Any] | None:
            if not (r.singers or r.songs or r.styles):
                return None
            next_p = p.copy()
            next_p["Page"] = next_p["Page"] + 1
            if r.songs:
                next_p["SongLastid"] = r.songs[-1].id
            if r.singers:
                next_p["SingersLastid"] = r.singers[-1].id
            if r.styles:
                next_p["StyleLastid"] = r.styles[-1].id
            return next_p

        return CgiRequestData(
            param=param,
            credential=credential,
            pager_strategy=MultiFieldContinuationStrategy[DislikeListData](
                build_next_params=_build_next_params,
            ),
        )

    async def add_dislike(self, id_type: int, values: list[int], *, credential: Credential | None = None) -> bool:
        """添加不喜欢.

        Args:
            id_type: 类型, 1=歌曲 / 2=歌手 / 3=风格.
            values:  对应的 ID 列表.
            credential: 登录凭证.

        Returns:
            是否操作成功.
        """
        keys = {1: "Songs", 2: "Singers", 3: "Styles"}
        result = await self._build_cgi(
            module="music.feedback.FeedbackBlack",
            method="AddDislike",
            param={keys[id_type]: [{"ID": str(vid), "IdType": id_type} for vid in values]},
            credential=credential,
            require_login=True,
        )
        return result.get("Retcode") == 0

    async def cancel_dislike(
        self,
        id_type: int,
        values: list[int],
        *,
        credential: Credential | None = None,
    ) -> bool:
        """取消不喜欢.

        Args:
            id_type:   类型, 1=歌曲 / 2=歌手 / 3=风格.
            values:    对应 ID 列表.
            credential: 登录凭证.

        Returns:
            是否操作成功.
        """
        keys = {1: "Songs", 2: "Singers", 3: "Styles"}
        result = await self._build_cgi(
            module="music.feedback.FeedbackBlack",
            method="CancelDislike",
            param={keys[id_type]: [{"ID": str(vid), "IdType": id_type} for vid in (values or [])]},
            credential=credential,
            require_login=True,
        )
        return result.get("Retcode") == 0

    async def cancel_all_dislike_song(self, *, credential: Credential | None = None) -> bool:
        """清空所有不喜欢歌曲.

        Args:
            credential: 登录凭证.

        Returns:
            是否操作成功.
        """
        result = await self._build_cgi(
            module="music.feedback.FeedbackBlack",
            method="CancelAllDislike",
            param={"ISOnlyGetToken": True},
            preserve_bool=True,
            credential=credential,
            require_login=True,
        )
        token = result.get("Token", "")
        result = await self._build_cgi(
            module="music.feedback.FeedbackBlack",
            method="CancelAllDislike",
            param={"DelType": 3, "Token": token},
            credential=credential,
            require_login=True,
        )
        return result.get("Retcode") == 0
