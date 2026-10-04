"""音响力模块测试."""

import pytest

from qqmusic_api import Client


@pytest.mark.core
def test_sound_power_request_data_assembly(client: Client) -> None:
    """测试音响力各接口参数拼装逻辑正确性."""
    req_detail = client.sound_power.get_detail()
    assert req_detail.module == "music.soundPower.SoundPowerSvr"
    assert req_detail.method == "QueryLevelDetailPage"
    assert req_detail.param == {}
    assert req_detail.require_login is True

    req_rule = client.sound_power.get_hugevip_rule()
    assert req_rule.module == "music.soundPower.SoundPowerSvr"
    assert req_rule.method == "QueryHugevipLevelRule"
    assert req_rule.param == {}
    assert req_rule.require_login is True
    req_rank = client.sound_power.get_friend_rank(offset=0, limit=10, last_uin="123", rankno=1)
    assert req_rank.module == "music.activeCenter.FriendRankSvr"
    assert req_rank.method == "GetRank"
    assert req_rank.param == {
        "rank_type": 1,
        "offset": 0,
        "limit": 10,
        "last_uin": "123",
        "rankno": 1,
    }
    assert req_rank.require_login is True
    req_like = client.sound_power.like_friend(uin="123456", cancel=False)
    assert req_like.module == "music.activeCenter.FriendRankSvr"
    assert req_like.method == "Like"
    assert req_like.param == {
        "rank_type": 1,
        "uin": "123456",
        "cancel": 0,
    }

    req_unlike = client.sound_power.like_friend(uin="123456", cancel=True)
    assert req_unlike.param["cancel"] == 1
    assert req_like.require_login is True
    req_privacy = client.sound_power.set_rank_privacy(status=1)
    assert req_privacy.module == "music.activeCenter.FriendRankSvr"
    assert req_privacy.method == "SetPrivacy"
    assert req_privacy.param == {"status": 1}
    assert req_privacy.require_login is True
    req_medal = client.sound_power.get_medal_entry(enc_uin="abc")
    assert req_medal.module == "music.medalHall.MedalHallEntrySrv"
    assert req_medal.method == "GetSoundPowerEntry"
    assert req_medal.param == {"EncUin": "abc"}
    assert req_medal.require_login is True
    req_tasks = client.sound_power.get_tasks()
    assert req_tasks.module == "music.activeCenter.ActTaskNewSvr"
    assert req_tasks.method == "GetTaskModules"
    assert req_tasks.param == {
        "actID": "1nsAQf",
        "taskModuleIDs": ["Z1jtHy7"],
    }
    assert req_tasks.require_login is True


async def test_get_detail_with_login(authenticated_client: Client) -> None:
    """测试已登录态下获取音响力主页详情数据模型."""
    result = await authenticated_client.sound_power.get_detail()
    assert result.power_info.level >= 0
    assert result.power_info.name != ""
    assert result.today_listen_time >= 0


async def test_get_friend_rank_with_login(authenticated_client: Client) -> None:
    """测试已登录态下获取好友听歌日榜数据模型."""
    result = await authenticated_client.sound_power.get_friend_rank(offset=0, limit=5)
    assert result.my_rank_no >= 0
    assert isinstance(result.ranks, list)


async def test_get_medal_entry_with_login(authenticated_client: Client) -> None:
    """测试已登录态下获取音响力勋章馆入口数据模型."""
    result = await authenticated_client.sound_power.get_medal_entry()
    assert result.title != ""
    assert result.medal_cnt >= 0
    assert isinstance(result.medal_list, list)
