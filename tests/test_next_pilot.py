"""Next 内核 Modules 层试点测试. 真实网络下验证新管道与旧路径行为一致."""

from collections.abc import Callable

from qqmusic_api import Client
from qqmusic_api.modules.song import SongFileInfo, SongFileType, SongQueryInfo
from qqmusic_api.next.endpoints.song import GET_SONG_DETAIL, QUERY_SONG, song_urls_endpoint
from qqmusic_api.next.pipeline import Pipeline, RequestEvent
from qqmusic_api.next.transport import NiquestsTransport
from tests.conftest import _call_with_skip


def _build_pipeline(client: Client, on_event: Callable[[RequestEvent], None] | None = None) -> Pipeline:
    """基于现有 Client 的上下文与会话构建试点管道.

    Args:
        client: 复用其上下文与会话配置的 Client 实例.
        on_event: 可选的观测事件收集回调.

    Returns:
        指向旧 Client 同一会话的试点管道.
    """
    return Pipeline(
        client._context,
        NiquestsTransport(
            client._session,
            proxies=client.proxies,
            hooks=client.hooks,
            cert=client.cert,
            verify=client.verify,
        ),
        on_event=on_event,
    )


async def test_pilot_get_detail_matches_legacy(client: Client) -> None:
    """测试新管道获取歌曲详情与旧路径结果及上游模块一致, 并标记 v2 流量路径."""
    descriptor = client.song.get_detail(100)
    endpoint = GET_SONG_DETAIL
    legacy = await descriptor

    events: list[RequestEvent] = []
    pipeline = _build_pipeline(client, on_event=events.append)
    pilot = await _call_with_skip(lambda: pipeline.execute(endpoint, descriptor.param))

    assert (descriptor.module, descriptor.method) == (endpoint.module, endpoint.method)
    assert pilot.track.id == legacy.track.id
    assert pilot.track.mid == legacy.track.mid
    # 限流重试会让 _call_with_skip 多次执行同一管道, 每次尝试都记录事件, 故只统计成功的那次.
    assert events, "管道未发出任何观测事件"
    success_events = [event for event in events if event.error is None]
    assert success_events == [events[-1]]
    assert success_events[0].path == "v2"
    assert success_events[0].endpoint == "music.pf_song_detail_svr/get_song_detail_yqq"


async def test_pilot_query_song_matches_legacy(client: Client) -> None:
    """测试新管道查询歌曲信息与旧路径结果及上游模块一致."""
    descriptor = client.song.query_song([SongQueryInfo(id=107479170)])
    endpoint = QUERY_SONG
    legacy = await descriptor
    pilot = await _call_with_skip(lambda: _build_pipeline(client).execute(endpoint, descriptor.param))

    assert (descriptor.module, descriptor.method) == (endpoint.module, endpoint.method)
    assert [track.mid for track in pilot.tracks] == [track.mid for track in legacy.tracks]


async def test_pilot_get_song_urls_matches_legacy(client: Client) -> None:
    """测试新管道获取歌曲链接与旧路径返回结构及稳定字段一致."""
    descriptor = client.song.get_song_urls([SongFileInfo(mid="003w2xz20QlUZt", file_type=SongFileType.MP3_128)])
    endpoint = song_urls_endpoint(SongFileType.MP3_128)
    legacy = await descriptor
    pilot = await _call_with_skip(lambda: _build_pipeline(client).execute(endpoint, descriptor.param))

    assert (descriptor.module, descriptor.method) == (endpoint.module, endpoint.method)
    assert len(pilot.data) == len(legacy.data) == 1
    # 只比对稳定字段: purl 与 vkey 由 CDN 调度即时签发, 鉴权后两条路径的取值不保证相同.
    assert [(item.mid, item.filename, item.result) for item in pilot.data] == [
        (item.mid, item.filename, item.result) for item in legacy.data
    ]
