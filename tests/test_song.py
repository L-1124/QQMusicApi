"""歌曲模块测试."""

import pytest

from qqmusic_api import Client
from qqmusic_api.core.exceptions import CgiApiException
from qqmusic_api.modules.song import EncryptedSongFileType, SongFileInfo, SongFileType, SongQueryInfo


@pytest.mark.parametrize(
    "value",
    [
        [SongQueryInfo(id=107479170)],
        [SongQueryInfo(mid="003w2xz20QlUZt")],
        [SongQueryInfo(id=107479170, song_type=1)],
        [SongQueryInfo(id=2314161, song_type=113)],
        [SongQueryInfo(id=107479170), SongQueryInfo(id=2314161, song_type=113)],
    ],
)
async def test_query_song(
    client: Client,
    value: list[SongQueryInfo],
) -> None:
    """测试查询歌曲信息."""
    try:
        result = await client.song.query_song(value)
        assert result.tracks
    except CgiApiException as e:
        if e.code == 103902:
            pytest.skip("特定特殊歌曲无权限或已下架 (103902)")
        else:
            raise


async def test_query_song_empty_value(client: Client) -> None:
    """测试空列表查询歌曲时抛出异常."""
    with pytest.raises(ValueError, match="song_info 不能为空"):
        await client.song.query_song([])


@pytest.mark.parametrize(
    "file_type",
    [
        SongFileType.MP3_128,
        SongFileType.FLAC,
        EncryptedSongFileType.FLAC,
    ],
)
async def test_get_song_urls(client: Client, file_type: SongFileType | EncryptedSongFileType) -> None:
    """测试获取歌曲文件链接."""
    result = await client.song.get_song_urls([SongFileInfo(mid="003w2xz20QlUZt", file_type=file_type)])
    assert len(result.data) == 1


def test_get_song_urls_exceed_limit(client: Client) -> None:
    """测试获取歌曲链接超出 mid 数量上限时抛出异常."""
    oversized = [SongFileInfo(mid="003w2xz20QlUZt")] * (client.song._GET_SONG_URLS_MAX_MID + 1)
    with pytest.raises(ValueError, match="mid 数量不能超过"):
        client.song.get_song_urls(oversized)


@pytest.mark.parametrize("value", [100, "003w2xz20QlUZt"])
async def test_get_detail(client: Client, value: int | str) -> None:
    """测试获取歌曲详情."""
    result = await client.song.get_detail(value)
    assert result.track.mid


async def test_get_similar_song(client: Client) -> None:
    """测试获取相似歌曲."""
    result = await client.song.get_similar_song(100)
    assert result.song


async def test_get_labels(client: Client) -> None:
    """测试获取歌曲标签."""
    result = await client.song.get_labels(100)
    assert result.labels is not None


async def test_get_related_songlist(client: Client) -> None:
    """测试获取歌曲相关歌单."""
    result = await client.song.get_related_songlist(100)
    assert result.songlist is not None


async def test_get_related_mv(client: Client) -> None:
    """测试获取歌曲相关 MV."""
    result = await client.song.get_related_mv(100)
    assert result.mv is not None


async def test_get_related_songlist_refresh(client: Client) -> None:
    """测试歌曲相关歌单支持换一批."""
    req1 = client.song.get_related_songlist(100)
    first_batch = await req1
    req2 = req1.next_request(first_batch)
    assert req2 is not None
    next_batch = await req2

    assert first_batch.songlist
    assert next_batch.songlist
    assert first_batch.songlist[0].id != next_batch.songlist[0].id


async def test_get_related_mv_refresh(client: Client) -> None:
    """测试歌曲相关 MV 支持换一批."""
    req1 = client.song.get_related_mv(1114857)
    first_batch = await req1
    req2 = req1.next_request(first_batch)
    assert req2 is not None
    next_batch = await req2

    assert first_batch.mv
    assert next_batch.mv
    assert first_batch.mv[-1].id != next_batch.mv[0].id


@pytest.mark.parametrize("value", [100, "003w2xz20QlUZt"])
async def test_get_other_version(client: Client, value: int | str) -> None:
    """测试获取歌曲其他版本."""
    result = await client.song.get_other_version(value)
    assert result.data is not None


@pytest.mark.parametrize("value", [100, "003w2xz20QlUZt"])
async def test_get_producer(client: Client, value: int | str) -> None:
    """测试获取制作人信息."""
    result = await client.song.get_producer(value)
    assert result.data is not None


async def test_get_sheet(client: Client) -> None:
    """测试获取歌曲相关曲谱."""
    result = await client.song.get_sheet("003w2xz20QlUZt")
    assert any(sheet.song_mid == "003w2xz20QlUZt" for sheet in result.result)


async def test_get_fav_num(client: Client) -> None:
    """测试获取歌曲收藏数量."""
    result = await client.song.get_fav_num([100])
    assert "100" in result.numbers


async def test_get_cdn_dispatch(client: Client) -> None:
    """测试获取音频 CDN 调度信息."""
    result = await client.song.get_cdn_dispatch()
    assert result.retcode == 0
    assert result.sip
    assert result.expiration > 0
    assert result.refresh_time > 0
    assert result.cache_time > 0
