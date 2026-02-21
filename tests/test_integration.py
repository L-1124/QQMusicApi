"""集成验证测试。"""

from qqmusic_api import Client, Credential
from qqmusic_api.core.request import Request


def test_client_module_access():
    """验证 Client 属性访问所有模块。"""
    client = Client()

    assert hasattr(client, "album")
    assert hasattr(client, "comment")
    assert hasattr(client, "mv")
    assert hasattr(client, "recommend")
    assert hasattr(client, "top")


def test_client_using_isolation():
    """验证 using() 保持模块访问并实现 Client 隔离。"""
    client1 = Client()
    cred = Credential(musicid=12345, musickey="test_key")
    client2 = client1.using(cred)

    assert client2 is not client1
    assert client2.credential is cred
    assert client1.credential.musicid != 12345

    # 验证模块访问
    assert client2.album._client is client2
    assert client1.album._client is client1


def test_album_methods():
    """验证 Album 模块方法返回 Request 对象。"""
    client = Client()

    # get_cover 返回 str, 不返回 Request
    assert isinstance(client.album.get_cover("002RaYvS3a4YvS"), str)

    # get_detail 返回 Request
    req_detail = client.album.get_detail("002RaYvS3a4YvS")
    assert isinstance(req_detail, Request)
    assert req_detail.module == "music.musichallAlbum.AlbumInfoServer"

    # get_song 返回 Request
    req_song = client.album.get_song("002RaYvS3a4YvS")
    assert isinstance(req_song, Request)
    assert req_song.module == "music.musichallAlbum.AlbumSongList"


def test_comment_methods():
    """验证 Comment 模块方法返回 Request 对象。"""
    client = Client()

    assert isinstance(client.comment.get_comment_count("003m8p9Z1v0T7b"), Request)
    assert isinstance(client.comment.get_hot_comments("003m8p9Z1v0T7b"), Request)
    assert isinstance(client.comment.get_new_comments("003m8p9Z1v0T7b"), Request)
    assert isinstance(client.comment.get_recommend_comments("003m8p9Z1v0T7b"), Request)
    assert isinstance(client.comment.get_moment_comments("003m8p9Z1v0T7b"), Request)


def test_mv_methods():
    """验证 MV 模块方法返回 Request 对象。"""
    client = Client()

    req_detail = client.mv.get_detail(["v0044o74422"])
    assert isinstance(req_detail, Request)
    assert req_detail.module == "video.VideoDataServer"

    req_urls = client.mv.get_mv_urls(["v0044o74422"])
    assert isinstance(req_urls, Request)
    assert req_urls.module == "music.stream.MvUrlProxy"


def test_recommend_methods():
    """验证 Recommend 模块方法返回 Request 对象。"""
    client = Client()

    assert isinstance(client.recommend.get_home_feed(), Request)
    assert isinstance(client.recommend.get_guess_recommend(), Request)
    assert isinstance(client.recommend.get_radar_recommend(), Request)
    assert isinstance(client.recommend.get_recommend_songlist(), Request)
    assert isinstance(client.recommend.get_recommend_newsong(), Request)


def test_top_methods():
    """验证 Top 模块方法返回 Request 对象。"""
    client = Client()

    req_cat = client.top.get_category()
    assert isinstance(req_cat, Request)
    assert req_cat.module == "music.musicToplist.Toplist"

    req_detail = client.top.get_detail(4)
    assert isinstance(req_detail, Request)
    assert req_detail.method == "GetDetail"
