"""推荐模块测试."""

from qqmusic_api import Client


async def test_get_home_feed(client: Client) -> None:
    """测试获取主页推荐响应模型."""
    result = await client.recommend.get_home_feed(page=1, direction=0, s_num=0, v_cache=[])
    assert result.shelves
    assert result.shelves[0].id > 0


async def test_get_guess_recommend(authenticated_client: Client) -> None:
    """测试猜你喜欢接口返回歌曲列表."""
    result = await authenticated_client.recommend.get_guess_recommend()
    assert all(song.mid for song in result.songs)


async def test_get_radar_recommend(client: Client) -> None:
    """测试获取雷达推荐响应模型."""
    result = await client.recommend.get_radar_recommend()
    assert result.songs
    assert result.songs[0].mid


async def test_get_recommend_songlist(client: Client) -> None:
    """测试获取推荐歌单响应模型."""
    result = await client.recommend.get_recommend_songlist(page=1, num=25)
    assert result.songlists
    assert result.songlists[0].title


async def test_get_recommend_newsong(client: Client) -> None:
    """测试获取推荐新歌响应模型."""
    result = await client.recommend.get_recommend_newsong()
    assert result.songs
    assert result.songs[0].mid
