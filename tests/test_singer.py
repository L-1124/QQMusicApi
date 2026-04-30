"""歌手模块测试."""

from qqmusic_api import Client
from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType, TabType


async def test_get_singer_list(client: Client) -> None:
    """测试获取歌手列表模型."""
    result = await client.singer.get_singer_list()
    assert result.singerlist
    assert result.singerlist[0].mid


async def test_get_singer_list_with_params(client: Client) -> None:
    """测试使用参数获取歌手列表模型."""
    result = await client.singer.get_singer_list(
        area=AreaType.CHINA,
        sex=SexType.MALE,
        genre=GenreType.POP,
    )
    assert result.area == AreaType.CHINA.value
    assert result.sex == SexType.MALE.value
    assert result.genre == GenreType.POP.value


async def test_get_singer_list_index(client: Client) -> None:
    """测试获取按索引分页的歌手列表模型."""
    result = await client.singer.get_singer_list_index()
    assert result.total > 0
    assert result.singerlist


async def test_get_singer_list_index_with_params(client: Client) -> None:
    """测试使用参数获取按索引分页的歌手列表模型."""
    result = await client.singer.get_singer_list_index(
        area=AreaType.CHINA,
        sex=SexType.FEMALE,
        genre=GenreType.POP,
        index=IndexType.Z,
        page=2,
        num=80,
    )
    assert result.index == IndexType.Z.value
    assert result.tags is not None


async def test_get_info(client: Client) -> None:
    """测试获取歌手主页基本信息模型."""
    result = await client.singer.get_info(mid="0025NhlN2yWrP4")
    assert result.singer.mid == "0025NhlN2yWrP4"
    assert result.base_info.name


async def test_get_tab_detail_wiki(client: Client) -> None:
    """测试获取歌手 Wiki Tab 详情模型."""
    result = await client.singer.get_tab_detail(
        mid="0025NhlN2yWrP4",
        tab_type=TabType.WIKI,
        page=1,
        num=10,
    )
    assert result.tab_id == TabType.WIKI.tab_id
    assert result.introduction_tab is not None


async def test_get_tab_detail_song(client: Client) -> None:
    """测试获取歌手歌曲 Tab 详情模型."""
    result = await client.singer.get_tab_detail(
        mid="0025NhlN2yWrP4",
        tab_type=TabType.SONG,
        page=1,
        num=10,
    )
    assert result.song_tab is not None
    assert result.song_tab


async def test_get_tab_detail_album(client: Client) -> None:
    """测试获取歌手专辑 Tab 详情模型."""
    result = await client.singer.get_tab_detail(
        mid="0025NhlN2yWrP4",
        tab_type=TabType.ALBUM,
        page=1,
        num=10,
    )
    assert result.album_tab is not None
    assert result.album_tab


async def test_get_tab_detail_video(client: Client) -> None:
    """测试获取歌手视频 Tab 详情模型."""
    result = await client.singer.get_tab_detail(
        mid="0025NhlN2yWrP4",
        tab_type=TabType.VIDEO,
        page=1,
        num=10,
    )
    assert result.video_tab is not None
    assert result.video_tab


async def test_get_desc(client: Client) -> None:
    """测试获取歌手描述信息模型."""
    result = await client.singer.get_desc(mids=["0025NhlN2yWrP4"])
    assert len(result.singer_list) == 1
    assert result.singer_list[0].basic_info.mid == "0025NhlN2yWrP4"


async def test_get_desc_multiple(client: Client) -> None:
    """测试获取多个歌手描述信息模型."""
    result = await client.singer.get_desc(mids=["0025NhlN2yWrP4", "001fNHEf1SFEFN"])
    assert len(result.singer_list) == 2


async def test_get_similar(client: Client) -> None:
    """测试获取相似歌手列表模型."""
    result = await client.singer.get_similar(mid="0025NhlN2yWrP4")
    assert result.singerlist
    assert result.singerlist[0].mid


async def test_get_similar_with_number(client: Client) -> None:
    """测试获取指定数量的相似歌手列表模型."""
    result = await client.singer.get_similar(mid="0025NhlN2yWrP4", number=5)
    assert len(result.singerlist) == 5


async def test_get_songs_list(client: Client) -> None:
    """测试获取歌手歌曲列表模型."""
    result = await client.singer.get_songs_list(mid="0025NhlN2yWrP4")
    assert result.total_num > 0
    assert result.song_list


async def test_get_songs_list_with_params(client: Client) -> None:
    """测试使用参数获取歌手歌曲列表模型."""
    result = await client.singer.get_songs_list(
        mid="0025NhlN2yWrP4",
        num=10,
        page=2,
    )
    assert result.song_list
    assert len(result.song_list) <= result.total_num


async def test_get_album_list(client: Client) -> None:
    """测试获取歌手专辑列表模型."""
    result = await client.singer.get_album_list(mid="0025NhlN2yWrP4")
    assert result.total > 0
    assert result.album_list


async def test_get_album_list_with_params(client: Client) -> None:
    """测试使用参数获取歌手专辑列表模型."""
    result = await client.singer.get_album_list(
        mid="0025NhlN2yWrP4",
        num=10,
        page=2,
    )
    assert result.album_list


async def test_get_mv_list(client: Client) -> None:
    """测试获取歌手 MV 列表模型."""
    result = await client.singer.get_mv_list(mid="0025NhlN2yWrP4")
    assert result.total > 0
    assert result.mv_list


async def test_get_mv_list_with_params(client: Client) -> None:
    """测试使用参数获取歌手 MV 列表模型."""
    result = await client.singer.get_mv_list(
        mid="0025NhlN2yWrP4",
        num=10,
        page=2,
    )
    assert result.mv_list
