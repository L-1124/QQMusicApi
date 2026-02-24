"""集成验证测试。"""

from qqmusic_api import Client, Credential
from qqmusic_api.core.request import Request


def test_client_module_access() -> None:
    """验证 Client 可访问全部已迁移模块。"""
    client = Client()

    assert hasattr(client, "album")
    assert hasattr(client, "comment")
    assert hasattr(client, "lyric")
    assert hasattr(client, "mv")
    assert hasattr(client, "recommend")
    assert hasattr(client, "search")
    assert hasattr(client, "singer")
    assert hasattr(client, "song")
    assert hasattr(client, "songlist")
    assert hasattr(client, "top")
    assert hasattr(client, "user")


def test_client_using_isolation() -> None:
    """验证 using() 后模块绑定到新 Client。"""
    client1 = Client()
    credential = Credential(musicid=12345, musickey="test_key")
    client2 = client1.using(credential)

    assert client2 is not client1
    assert client2.credential is credential
    assert client2.album._client is client2
    assert client2.lyric._client is client2
    assert client2.singer._client is client2
    assert client2.song._client is client2
    assert client2.songlist._client is client2
    assert client2.user._client is client2
    assert client1.song._client is client1


def test_module_method_completeness() -> None:
    """验证模块方法清单完整且不包含被删除 helper。"""
    client = Client()

    expected_methods = {
        "lyric": ["get_lyric"],
        "songlist": ["get_detail", "create", "delete", "add_songs", "del_songs"],
        "singer": [
            "get_singer_list",
            "get_singer_list_index",
            "get_info",
            "get_tab_detail",
            "get_desc",
            "get_similar",
            "get_songs_list",
            "get_album_list",
            "get_mv_list",
        ],
        "song": [
            "query_song",
            "get_try_url",
            "get_detail",
            "get_similar_song",
            "get_lables",
            "get_related_songlist",
            "get_related_mv",
            "get_other_version",
            "get_producer",
            "get_sheet",
            "get_fav_num",
        ],
        "user": [
            "get_euin",
            "get_musicid",
            "get_homepage",
            "get_vip_info",
            "get_follow_singers",
            "get_fans",
            "get_friend",
            "get_follow_user",
            "get_created_songlist",
            "get_fav_song",
            "get_fav_songlist",
            "get_fav_album",
            "get_fav_mv",
            "get_music_gene",
        ],
    }

    for module_name, methods in expected_methods.items():
        module = getattr(client, module_name)
        for method in methods:
            assert hasattr(module, method), f"missing {module_name}.{method}"

    assert not hasattr(client.songlist, "get_songlist")
    assert not hasattr(client.singer, "get_singer_list_index_all")
    assert not hasattr(client.singer, "get_songs")
    assert not hasattr(client.singer, "get_songs_list_all")
    assert not hasattr(client.singer, "get_album_list_all")
    assert not hasattr(client.singer, "get_mv_list_all")
    assert not hasattr(client.song, "get_song_urls")


def test_new_module_methods_return_request() -> None:
    """验证新增模块原子 API 返回 Request 对象。"""
    client = Client()

    assert isinstance(client.lyric.get_lyric("002mZevo3wHvsc"), Request)
    assert isinstance(client.songlist.get_detail(1), Request)
    assert isinstance(client.song.query_song(["002mZevo3wHvsc"]), Request)
    assert isinstance(client.singer.get_info("002J4UUk29y8BY"), Request)
    assert isinstance(client.user.get_musicid("euin"), Request)
