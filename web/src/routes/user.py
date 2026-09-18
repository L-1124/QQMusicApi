"""用户 Web 路由契约."""

from qqmusic_api.modules.user import UserApi

from ..routing.route_types import AuthPolicy, HttpMethod, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(
        UserApi.get_created_songlist,
        "/user/{uin}/created_songlists",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        UserApi.get_fans,
        "/user/{euin}/fans",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        UserApi.get_fav_album,
        "/user/{euin}/fav/albums",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        UserApi.get_fav_mv,
        "/user/{euin}/fav/mvs",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        UserApi.get_fav_song,
        "/user/{euin}/fav/songs",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        UserApi.get_fav_songlist,
        "/user/{euin}/fav/songlists",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        UserApi.get_follow_singers,
        "/user/{euin}/follow/singers",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        UserApi.get_follow_user,
        "/user/{euin}/follow/users",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        UserApi.get_friend,
        "/user/get_friend",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        UserApi.get_homepage,
        "/user/{euin}/homepage",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        UserApi.get_music_gene,
        "/user/{euin}/music_gene",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(UserApi.get_vip_info, "/user/get_vip_info", auth=AuthPolicy.COOKIE_OR_DEFAULT),
    # 收藏/取消收藏歌单
    R(
        "user",
        "fav_songlist",
        "/user/fav/songlists",
        bool,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="收藏歌单",
        description="收藏他人的公开歌单至当前账号.歌单已在收藏中也返回成功.",
    ),
    R(
        "user",
        "unfav_songlist",
        "/user/fav/songlists/{songlist_id}",
        bool,
        methods=(HttpMethod.DELETE,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="取消收藏歌单",
        description="取消收藏他人的公开歌单.歌单本就不在收藏中也返回成功.",
    ),
    # 不喜欢
    R(
        UserApi.get_dislike_list,
        "/user/dislikes",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取不喜欢列表",
        description="获取用户的不喜欢列表, 支持按类型和分页筛选.",
    ),
    R(
        "user",
        "add_dislike",
        "/user/dislikes",
        bool,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="添加不喜欢",
        description="添加不喜欢项 (歌曲/歌手/风格).",
    ),
    R(
        "user",
        "cancel_dislike",
        "/user/dislikes",
        bool,
        methods=(HttpMethod.DELETE,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="取消不喜欢",
        description="取消不喜欢项 (歌曲/歌手/风格).",
    ),
    R(
        "user",
        "cancel_all_dislike_song",
        "/user/dislikes/songs",
        bool,
        methods=(HttpMethod.DELETE,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="清空所有不喜欢歌曲",
        description="清空用户的所有不喜欢歌曲列表.",
    ),
)
