"""音响力 Web 路由契约."""

from qqmusic_api.modules.sound_power import SoundPowerApi

from ..routing.route_types import AuthPolicy, HttpMethod, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(
        SoundPowerApi.get_detail,
        "/sound_power/detail",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取音响力等级主页与今日听歌时长",
        description="查询当前登录用户的音响力等级 (S0-Sn)、今日累计有效听歌秒数及解锁权益.",
    ),
    R(
        SoundPowerApi.get_hugevip_rule,
        "/sound_power/hugevip_rule",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取超级会员音响力加速与等级规则",
        description="查询超级会员 1.5 倍音响力成长值加速规则及各等级对应听歌时长要求.",
    ),
    R(
        SoundPowerApi.get_friend_rank,
        "/sound_power/friend_rank",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取好友听歌日榜列表",
        description="分页查询微信或 QQ 好友今日听歌物理时长排行, 以及个人在榜单中的名次与获赞数.",
    ),
    R(
        SoundPowerApi.like_friend,
        "/sound_power/like",
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="点赞或取消点赞好友听歌榜",
        description="为好友听歌日榜中的指定好友条目点赞, 或取消已有点赞.",
    ),
    R(
        SoundPowerApi.set_rank_privacy,
        "/sound_power/privacy",
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="设置好友排行榜隐私状态",
        description="设置当前账号在好友听歌日榜中的隐私可见性.",
    ),
    R(
        SoundPowerApi.get_medal_entry,
        "/sound_power/medal_entry",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取音响力勋章馆入口与佩戴勋章",
        description="查询音响力勋章馆入口信息, 包括已点亮听歌勋章数量及当前佩戴展示的勋章.",
    ),
    R(
        SoundPowerApi.get_tasks,
        "/sound_power/tasks",
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="获取音响力加速任务模块",
        description="查询当前音响力加速活动任务列表.",
    ),
)
