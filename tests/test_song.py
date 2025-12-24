import pytest

from qqmusic_api import song

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_query_song():
    assert await song.query_song(["004emQMs09Z1lz"])


async def test_get_detail():
    assert await song.get_detail("004emQMs09Z1lz")
    assert await song.get_detail(680279)


async def test_get_related_mv():
    assert await song.get_related_mv(680279)


async def test_get_producer():
    assert await song.get_producer("004emQMs09Z1lz")
    assert await song.get_producer(680279)


async def test_get_labels():
    assert await song.get_lables(680279)


async def test_get_sheet():
    assert await song.get_sheet("004emQMs09Z1lz")


async def test_get_related_songlist():
    assert await song.get_related_songlist(680279)


async def test_get_similar_songs():
    assert await song.get_similar_song(680279)


async def test_get_other_version():
    assert await song.get_other_version("004emQMs09Z1lz")
    assert await song.get_other_version(680279)


async def test_get_song_urls():
    assert await song.get_song_urls(["0023CVP23SH17s"])
    # get_try_url 可能返回空字符串（当歌曲没有试听版本或 API 无法获取时）
    result = await song.get_try_url("00041h1u3kgquE", "062sn0lg3VGZad")
    assert isinstance(result, str)


async def test_get_fav_num():
    assert await song.get_fav_num(songid=[438910555, 9063002])
