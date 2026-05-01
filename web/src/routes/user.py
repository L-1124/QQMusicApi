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
from ._helpers import EUIN, UIN, USER_PAGE, R

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
        "/user/{euin}/fans",
        UserRelationListResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_album",
        "/user/{euin}/fav/albums",
        UserFavAlbumResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_mv",
        "/user/{euin}/fav/mvs",
        UserFavMvResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_song",
        "/user/{euin}/fav/songs",
        GetSonglistDetailResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_fav_songlist",
        "/user/{euin}/fav/songlists",
        UserFavSonglistResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_follow_singers",
        "/user/{euin}/follow/singers",
        UserRelationListResponse,
        params=(*EUIN, *USER_PAGE),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_follow_user",
        "/user/{euin}/follow/users",
        UserRelationListResponse,
        params=(*EUIN, *USER_PAGE),
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
        "/user/{euin}/homepage",
        UserHomepageResponse,
        params=EUIN,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "user",
        "get_music_gene",
        "/user/{euin}/music_gene",
        UserMusicGeneResponse,
        params=EUIN,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R("user", "get_vip_info", "/user/get_vip_info", UserVipInfoResponse, auth=AuthPolicy.COOKIE_OR_DEFAULT),
)
