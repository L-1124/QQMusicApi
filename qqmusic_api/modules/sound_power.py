"""音响力与听歌榜相关 API."""

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..models.request import Credential
from ..models.sound_power import (
    ActTaskModulesResponse,
    FriendRankResponse,
    HugevipLevelRuleResponse,
    LikeFriendResponse,
    SetRankPrivacyResponse,
    SoundPowerDetailResponse,
    SoundPowerMedalEntryResponse,
)
from ._base import ApiModule


class SoundPowerApi(ApiModule):
    """音响力等级、成长特权与好友听歌日榜 API."""

    @cgi_endpoint(
        key="sound_power.get_detail",
        module="music.soundPower.SoundPowerSvr",
        method="QueryLevelDetailPage",
        response_model=SoundPowerDetailResponse,
        require_login=True,
    )
    def get_detail(self, *, credential: Credential | None = None) -> CgiRequestData:
        """获取用户当前音响力等级主页、今日听歌时长及权益.

        Args:
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(param={}, credential=credential)

    @cgi_endpoint(
        key="sound_power.get_hugevip_rule",
        module="music.soundPower.SoundPowerSvr",
        method="QueryHugevipLevelRule",
        response_model=HugevipLevelRuleResponse,
        require_login=True,
    )
    def get_hugevip_rule(self, *, credential: Credential | None = None) -> CgiRequestData:
        """获取超级会员音响力加速与等级规则.

        Args:
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(param={}, credential=credential)

    @cgi_endpoint(
        key="sound_power.get_friend_rank",
        module="music.activeCenter.FriendRankSvr",
        method="GetRank",
        response_model=FriendRankResponse,
        require_login=True,
    )
    def get_friend_rank(
        self,
        offset: int = 0,
        limit: int = 10,
        last_uin: str = "",
        rankno: int = 0,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取好友听歌日榜列表.

        Args:
            offset: 分页偏移量.
            limit: 每页获取数量.
            last_uin: 上一页最后一条好友的 UIN.
            rankno: 榜单流水号或批次号 (首次请求可传 0).
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(
            param={
                "rank_type": 1,
                "offset": offset,
                "limit": limit,
                "last_uin": last_uin,
                "rankno": rankno,
            },
            credential=credential,
        )

    @cgi_endpoint(
        key="sound_power.like_friend",
        module="music.activeCenter.FriendRankSvr",
        method="Like",
        response_model=LikeFriendResponse,
        require_login=True,
    )
    def like_friend(
        self,
        uin: str,
        *,
        cancel: bool = False,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """为好友听歌榜条目点赞或取消点赞.

        Args:
            uin: 目标好友的 UIN.
            cancel: 是否为取消点赞 (False 为点赞, True 为取消点赞).
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(
            param={
                "rank_type": 1,
                "uin": uin,
                "cancel": 1 if cancel else 0,
            },
            credential=credential,
        )

    @cgi_endpoint(
        key="sound_power.set_rank_privacy",
        module="music.activeCenter.FriendRankSvr",
        method="SetPrivacy",
        response_model=SetRankPrivacyResponse,
        require_login=True,
    )
    def set_rank_privacy(
        self,
        status: int = 0,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """设置好友排行榜隐私状态.

        Args:
            status: 隐私开关状态.
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(
            param={"status": status},
            credential=credential,
        )

    @cgi_endpoint(
        key="sound_power.get_medal_entry",
        module="music.medalHall.MedalHallEntrySrv",
        method="GetSoundPowerEntry",
        response_model=SoundPowerMedalEntryResponse,
        require_login=True,
    )
    def get_medal_entry(
        self,
        enc_uin: str = "",
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取音响力勋章馆入口与佩戴勋章信息.

        Args:
            enc_uin: 加密的 UIN (未传入时默认为空字符串).
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(
            param={"EncUin": enc_uin},
            credential=credential,
        )

    @cgi_endpoint(
        key="sound_power.get_tasks",
        module="music.activeCenter.ActTaskNewSvr",
        method="GetTaskModules",
        response_model=ActTaskModulesResponse,
        require_login=True,
    )
    def get_tasks(
        self,
        act_id: str = "1nsAQf",
        task_module_ids: list[str] | None = None,
        *,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """获取音响力加速任务模块.

        Args:
            act_id: 活动 ID (默认为 '1nsAQf').
            task_module_ids: 任务模块 ID 列表 (默认为 ['Z1jtHy7']).
            credential: 可选的登录凭证; 缺省时使用客户端全局凭证.
        """
        return CgiRequestData(
            param={
                "actID": act_id,
                "taskModuleIDs": task_module_ids if task_module_ids is not None else ["Z1jtHy7"],
            },
            credential=credential,
        )
