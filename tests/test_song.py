"""歌曲模块测试."""

import pytest

from qqmusic_api import Client
from qqmusic_api.modules.song import EncryptedSongFileType, SongFileType


@pytest.mark.parametrize("value", [[100], ["003w2xz20QlUZt"]])
async def test_query_song(client: Client, value: list[int] | list[str]) -> None:
    """测试查询歌曲信息."""
    result = await client.song.query_song(value)
    assert result.tracks


async def test_query_song_empty_value(client: Client) -> None:
    """测试空列表查询歌曲时抛出异常."""
    with pytest.raises(ValueError, match="value 不能为空"):
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
    result = await client.song.get_song_urls(mid=["003w2xz20QlUZt"], file_type=file_type)
    assert len(result.data) == 1


async def test_get_song_urls_empty(client: Client) -> None:
    """测试空列表获取歌曲链接返回空结果集."""
    result = await client.song.get_song_urls(mid=[])
    assert result.data == []


@pytest.mark.parametrize("value", [100, "003w2xz20QlUZt"])
async def test_get_detail(client: Client, value: int | str) -> None:
    """测试获取歌曲详情."""
    result = await client.song.get_detail(value)
    assert result.track.mid


async def test_get_similar_song(client: Client) -> None:
    """测试获取相似歌曲."""
    result = await client.song.get_similar_song(100)
    assert result.song


async def test_get_lables(client: Client) -> None:
    """测试获取歌曲标签."""
    result = await client.song.get_lables(100)
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
    refresher = client.song.get_related_songlist(100).refresh()
    first_batch = await refresher.first()
    next_batch = await refresher.refresh()

    assert first_batch.songlist
    assert next_batch.songlist
    assert first_batch.songlist[0].id != next_batch.songlist[0].id


async def test_get_related_mv_refresh(client: Client) -> None:
    """测试歌曲相关 MV 支持换一批."""
    refresher = client.song.get_related_mv(1114857).refresh()
    first_batch = await refresher.first()
    next_batch = await refresher.refresh()

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
