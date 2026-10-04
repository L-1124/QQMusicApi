"""音响力等级查询与听歌时长上报示例."""

import asyncio
import base64
import gzip
import hashlib
import json
import time
import zlib
from typing import Any, cast

from qqmusic_api import Client, Credential, Platform
from qqmusic_api.core.request import HttpRequest
from qqmusic_api.modules.song import SongFileInfo, SongFileType, SpecialSongFileType

MUSICID = 0
MUSICKEY = ""
LOGIN_TYPE = 2

credential = Credential(
    musicid=MUSICID,
    musickey=MUSICKEY,
    login_type=LOGIN_TYPE,
)


async def report_play_duration(
    client: Client,
    song_id: int,
    audio_time_ms: int,
    play_duration_seconds: int,
    vkey: str,
    co_singer: str = "",
    singer_id: int = 0,
) -> bool:
    """向 imusic_tj 网关提交听歌物理流水."""
    cgi_exec = cast("Any", client._engine)._cgi
    device = await cgi_exec._device_store.get_device()
    session = await cgi_exec._android_session.ensure()
    comm = client.version_policy.build_comm(
        platform=Platform.ANDROID,
        credential=client.credential,
        device=device,
        qimei=await cgi_exec._qimei_manager.get_cached(),
        guid=device.open_udid,
        session=session,
    )

    optime = int(time.time())
    user_qq = str(client.credential.musicid or "")
    timekey = hashlib.md5(f"{optime}{play_duration_seconds}{user_qq}gk2$Lh-&l4#!4iow".encode()).hexdigest().upper()
    string27 = base64.b64encode(
        json.dumps(
            {
                "screen_on": 1,
                "app_in": 1,
                "app_time": play_duration_seconds,
                "playpage_time": int(play_duration_seconds * 0.4),
                "tag_id": 10001,
                "tag_type": 15,
                "start_playtype": 0,
                "start_playtime": 0,
            },
            separators=(",", ":"),
        ).encode()
    ).decode()

    item = (
        f'<item cmd="1" optime="{optime}" nettype="1030" QQ="{user_qq}" uid="{session.uid}" '
        f'os="{device.version.release}" model="{device.model}" version="20.8.0.8" songtype="1" playtype="5" from="8," '
        f'openstore="0" crytype="2" paytype="1" hijackflag="1001" desktoplyric="0" '
        f'playdevice="0" playlist_mode="0" outdev="0" url="16" playmode="1" repeat_times="-1" '
        f'string25="free" string26="n" string29="0" supersound="5" cdn="" cdnip="" '
        f'hasFirstBuffer="3" filetype="4" err="0" time2="161" issoftdecode="1" component_type="-1" '
        f'wait_time="325" player_retry="0" audiotime="{audio_time_ms}" timekey="{timekey}" '
        f'co_singer="{co_singer}" vkey="{vkey}" time="{play_duration_seconds}" '
        f'play_duration_mi="{play_duration_seconds * 1000}" errcode="" play_speed="1.0" vip_level="69632" '
        f'audio_effect="0:0" string27="{string27}" '
        f'songid="{song_id}" singerid="{singer_id}" fversion="0" buildver="1"/>'
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\r\n<root>\r\n'
        + "".join(f"    <{k}>{v}</{k}>\r\n" for k, v in comm.items())
        + f"    <cid>228</cid>\r\n    {item}\r\n</root>"
    )

    resp = await client.execute(
        HttpRequest(
            _executor=client,
            method="POST",
            url="https://stat6.y.qq.com/android/fcgi-bin/imusic_tj",
            data=gzip.compress(xml.encode()),
            headers={
                "User-Agent": client.version_policy.get_user_agent(Platform.ANDROID, device),
                "Content-Encoding": "gzip",
                "Host": "stat6.y.qq.com",
                "Accept": "*/*",
            },
            raw=True,
        )
    )
    if resp.status_code == 200 and len(resp.content) > 5 and resp.content[:5] == b"\x00" * 5:
        return json.loads(zlib.decompress(resp.content[5:]).decode("utf-8", errors="replace")).get("code") == 0
    return False


async def main() -> None:
    """运行音响力等级查询与听歌时长上报示例."""
    if not credential.musicid or not credential.musickey:
        print("请先配置 MUSICID 与 MUSICKEY。")
        return

    async with Client(credential) as client:
        detail = await client.sound_power.get_detail()
        print(f"用户昵称: {detail.nick}")
        print(f"当前等级: {detail.power_info.name} (S{detail.power_info.level})")
        print(f"今日时长: {detail.today_listen_time} 秒 ({detail.today_listen_time // 60} 分钟)")
        print(f"等级进度: {detail.power_info.value} / {detail.power_info.next_value}")

        rank = await client.sound_power.get_friend_rank(offset=0, limit=5)
        print(f"好友榜排名: 第 {rank.my_rank_no} 名, 今日听歌: {rank.my_play_time} 秒")
        for f in rank.ranks:
            print(f"  #{f.no} {f.nick} ({f.uin}) - {f.play_time // 60} 分钟 [{f.sp_info.get('name', '未上榜')}]")

        medal = await client.sound_power.get_medal_entry()
        print(f"{medal.title}: 已点亮 {medal.medal_cnt} 枚勋章")

        track = (await client.song.get_detail("0039MnYb0qxYhV")).track
        urls = await client.song.get_song_urls([SongFileInfo(mid=track.mid)], file_type=SongFileType.MP3_128)
        vkey = urls.data[0].vkey if urls.data and urls.data[0].result == 0 else ""
        if not vkey:
            trial = await client.song.get_song_urls([SongFileInfo(mid=track.mid)], file_type=SpecialSongFileType.TRY)
            vkey = trial.data[0].vkey if trial.data else ""

        if not vkey:
            print(f"未能获取到歌曲 {track.name} 的播放凭证。")
            return

        ok = await report_play_duration(
            client=client,
            song_id=track.id,
            audio_time_ms=track.interval * 1000,
            play_duration_seconds=60,
            vkey=vkey,
            co_singer=track.singer[0].name if track.singer else "",
            singer_id=track.singer[0].id if track.singer else 0,
        )
        print(f"上报结果: {'成功' if ok else '失败'}")


if __name__ == "__main__":
    asyncio.run(main())
