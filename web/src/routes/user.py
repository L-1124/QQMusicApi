"""用户 Web 路由契约."""

from qqmusic_api.models.songlist import GetSonglistDetailResponse
from qqmusic_api.models.user import (
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

from ..routing.route_types import AuthPolicy, WebRoute
from ._helpers import ENCRYPT_UIN, UIN, USER_PAGE, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "user",
        "get_created_songlist",
        "/user/{uin}/created_songlists",
        UserCreatedSonglistResponse,
        params=UIN,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fans",
        "/user/{encrypt_uin}/fans",
        UserRelationListResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_album",
        "/user/{encrypt_uin}/fav/albums",
        UserFavAlbumResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_mv",
        "/user/{encrypt_uin}/fav/mvs",
        UserFavMvResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_song",
        "/user/{encrypt_uin}/fav/songs",
        GetSonglistDetailResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_songlist",
        "/user/{encrypt_uin}/fav/songlists",
        UserFavSonglistResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_follow_singers",
        "/user/{encrypt_uin}/follow/singers",
        UserRelationListResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_follow_user",
        "/user/{encrypt_uin}/follow/users",
        UserRelationListResponse,
        params=(*ENCRYPT_UIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_friend",
        "/user/get_friend",
        UserFriendListResponse,
        params=USER_PAGE,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_homepage",
        "/user/{encrypt_uin}/homepage",
        UserHomepageResponse,
        params=ENCRYPT_UIN,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_music_gene",
        "/user/{encrypt_uin}/music_gene",
        UserMusicGeneResponse,
        params=ENCRYPT_UIN,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R("user", "get_vip_info", "/user/get_vip_info", UserVipInfoResponse, auth=AuthPolicy.COOKIE_OR_DEFAULT),
)
