"""Next 内核 Modules 层试点测试. 真实网络下验证新管道与旧路径行为一致."""

from qqmusic_api import Client
from qqmusic_api.modules.song import SongFileInfo, SongFileType, SongQueryInfo
from qqmusic_api.next.endpoints.song import GET_SONG_DETAIL, QUERY_SONG, song_urls_endpoint
from qqmusic_api.next.pipeline import Pipeline
from qqmusic_api.next.transport import NiquestsTransport
from tests.conftest import _call_with_skip


def _build_pipeline(client: Client) -> Pipeline:
    """基于现有 Client 的上下文与会话构建试点管道."""
    return Pipeline(
        client._context,
        NiquestsTransport(
            client._session,
            proxies=client.proxies,
            hooks=client.hooks,
            cert=client.cert,
            verify=client.verify,
        ),
    )


async def test_pilot_get_detail_matches_legacy(client: Client) -> None:
    """测试新管道获取歌曲详情与旧路径结果一致."""
    descriptor = client.song.get_detail(100)
    legacy = await descriptor
    pilot = await _call_with_skip(lambda: _build_pipeline(client).execute(GET_SONG_DETAIL, descriptor.param))

    assert pilot.track.id == legacy.track.id
    assert pilot.track.mid == legacy.track.mid


async def test_pilot_query_song_matches_legacy(client: Client) -> None:
    """测试新管道查询歌曲信息与旧路径结果一致."""
    descriptor = client.song.query_song([SongQueryInfo(id=107479170)])
    legacy = await descriptor
    pilot = await _call_with_skip(lambda: _build_pipeline(client).execute(QUERY_SONG, descriptor.param))

    assert [track.mid for track in pilot.tracks] == [track.mid for track in legacy.tracks]


async def test_pilot_get_song_urls_matches_legacy(client: Client) -> None:
    """测试新管道获取歌曲链接与旧路径返回结构一致."""
    descriptor = client.song.get_song_urls([SongFileInfo(mid="003w2xz20QlUZt", file_type=SongFileType.MP3_128)])
    legacy = await descriptor
    pilot = await _call_with_skip(
        lambda: _build_pipeline(client).execute(song_urls_endpoint(SongFileType.MP3_128), descriptor.param)
    )

    assert len(pilot.data) == len(legacy.data) == 1
