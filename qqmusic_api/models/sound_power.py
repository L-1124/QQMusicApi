"""音响力与听歌榜相关数据模型."""

from typing import Any

from pydantic import Field

from .request import Response


class SoundPowerEquity(Response):
    """音响力等级特权项.

    Attributes:
        etype: 特权类型编码.
        name: 特权名称.
        icon: 特权图标链接.
        scheme: 跳转链接.
    """

    etype: int = Field(default=0, validation_alias="eType")
    name: str = ""
    icon: str = ""
    scheme: str = ""


class SoundPowerInfo(Response):
    """音响力基础信息.

    Attributes:
        level: 当前等级数字 (0 对应 S0).
        value: 累计数值.
        name: 等级称号.
        icon: 等级图标.
        current_value: 当前等级区间累计值.
        next_value: 升级至下一等级所需总阈值.
        reach_max_level: 是否达到最高等级.
        is_huge_vip: 是否激活超级会员加成.
        next_level_nums: 升级称号所需人数或参数.
        next_level_icon: 下一等级图标.
    """

    level: int = 0
    value: int = 0
    name: str = ""
    icon: str = ""
    current_value: int = Field(default=0, validation_alias="currentValue")
    next_value: int = Field(default=0, validation_alias="nextValue")
    reach_max_level: int = Field(default=0, validation_alias="reachMaxLevel")
    is_huge_vip: bool = Field(default=False, validation_alias="isHugeVip")
    next_level_nums: int = Field(default=0, validation_alias="nextLevelNums")
    next_level_icon: str = Field(default="", validation_alias="nextLevelIcon")


class SoundPowerDetailResponse(Response):
    """音响力等级主页响应数据.

    Attributes:
        power_info: 音响力基础等级信息.
        medal_num: 拥有勋章数量.
        nick: 用户昵称.
        head_pic: 头像图片链接.
        today_listen_time: 今日累计有效听歌时间 (秒).
        equity_text: 特权文本提示.
        equities: 解锁及未解锁特权列表.
        is_hugevip: 是否为超级会员 (1 为是).
        hugevip_power_info: 超级会员专属加速信息.
        medal_info: 佩戴勋章信息.
    """

    power_info: SoundPowerInfo = Field(default_factory=SoundPowerInfo, validation_alias="powerInfo")
    medal_num: int = Field(default=0, validation_alias="medalNum")
    nick: str = ""
    head_pic: str = Field(default="", validation_alias="headPic")
    today_listen_time: int = Field(default=0, validation_alias="todayLT")
    equity_text: str = Field(default="", validation_alias="equityText")
    equities: list[SoundPowerEquity] = Field(default_factory=list)
    is_hugevip: int = Field(default=0, validation_alias="isHugevip")
    hugevip_power_info: dict[str, Any] | None = Field(default=None, validation_alias="hugevipPowerInfo")
    medal_info: dict[str, Any] | None = Field(default=None, validation_alias="medalInfo")


class HugevipLevelRuleItem(Response):
    """超会等级规则条目.

    Attributes:
        level: 等级数字.
        name: 等级名称.
        icon: 等级图标.
        need_duration: 升级所需时长 (分钟).
        percent: 对应加速百分比.
    """

    level: int = 0
    name: str = ""
    icon: str = ""
    need_duration: int = Field(default=0, validation_alias="needDuration")
    percent: str = ""


class HugevipLevelRuleResponse(Response):
    """超级会员音响力加速与等级规则响应.

    Attributes:
        current_duration: 当前已达成有效物理时长.
        next_level_duration: 升级下一阶段所需时长.
        rules: 规则列表.
    """

    current_duration: int = Field(default=0, validation_alias="currentDuration")
    next_level_duration: int = Field(default=0, validation_alias="nextLevelDuration")
    rules: list[HugevipLevelRuleItem] = Field(default_factory=list)


class FriendRankItem(Response):
    """好友听歌日榜单条目.

    Attributes:
        uin: 好友 UIN.
        nick: 好友昵称.
        pic: 头像链接.
        play_time: 听歌物理累计时间 (秒).
        like_num: 获赞数量.
        like_status: 当前用户点赞状态 (0 为未点赞, 1 为已赞).
        no: 榜单排名 (1 为第一名).
        sp_info: 音响力等级快照.
        medal_info: 佩戴勋章快照.
    """

    uin: str = ""
    nick: str = ""
    pic: str = ""
    play_time: int = 0
    like_num: int = 0
    like_status: int = 0
    no: int = 0
    sp_info: dict[str, Any] = Field(default_factory=dict, validation_alias="spInfo")
    medal_info: dict[str, Any] = Field(default_factory=dict, validation_alias="mInfo")


class FriendRankResponse(Response):
    """好友听歌日榜响应数据.

    Attributes:
        ranks: 好友排行列表.
        my_rank_no: 当前用户在好友榜的排名.
        my_play_time: 当前用户今日听歌秒数.
        my_like_num: 当前用户获赞总数.
        has_more: 是否还有更多好友 (0 为否, 1 为是).
        rankno: 榜单流水号或批次号.
    """

    ranks: list[FriendRankItem] = Field(default_factory=list)
    my_rank_no: int = 0
    my_play_time: int = 0
    my_like_num: int = 0
    has_more: int = 0
    rankno: int = 0


class LikeFriendResponse(Response):
    """好友听歌榜点赞操作响应.

    Attributes:
        no_use: 状态占位符.
    """

    no_use: int = Field(default=0, validation_alias="NOUSE")


class SetRankPrivacyResponse(Response):
    """好友排行榜隐私状态设置响应.

    Attributes:
        status: 设置后的隐私开关状态.
    """

    status: int = 0


class SoundPowerMedalItem(Response):
    """听歌勋章条目.

    Attributes:
        pic_url: 勋章图标 URL.
        scheme: 点击跳转 Scheme.
    """

    pic_url: str = Field(default="", validation_alias="PicURL")
    scheme: str = Field(default="", validation_alias="Scheme")


class SoundPowerMedalEntryResponse(Response):
    """音响力勋章馆入口响应数据.

    Attributes:
        title: 模块标题 (如 '听歌勋章').
        medal_cnt: 点亮勋章总数.
        medal_list: 勋章展示列表.
    """

    title: str = Field(default="", validation_alias="Title")
    medal_cnt: int = Field(default=0, validation_alias="MedalCnt")
    medal_list: list[SoundPowerMedalItem] = Field(default_factory=list, validation_alias="MedalList")


class ActTaskModulesResponse(Response):
    """音响力加速任务响应.

    Attributes:
        ret_code: 结果状态码.
        ret_msg: 结果信息.
        task_modules: 任务模块列表.
        act_info: 活动元数据.
    """

    ret_code: int = Field(default=0, validation_alias="retCode")
    ret_msg: str = Field(default="", validation_alias="retMsg")
    task_modules: list[dict[str, Any]] | None = Field(default=None, validation_alias="taskModules")
    act_info: dict[str, Any] = Field(default_factory=dict, validation_alias="actInfo")
