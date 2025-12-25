import pytest

from qqmusic_api import recommend

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_home_feed():
    assert await recommend.get_home_feed()


async def test_get_guess_recommend():
    assert await recommend.get_guess_recommend()


async def test_get_radar_recommend():
    assert await recommend.get_radar_recommend()


async def test_get_recommend_songlist():
    assert await recommend.get_recommend_songlist()


async def test_get_recommend_newsong():
    assert await recommend.get_recommend_newsong()
