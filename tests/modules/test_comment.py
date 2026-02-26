"""评论模块测试."""

import pytest

from qqmusic_api.modules.comment import CommentApi


@pytest.mark.anyio
async def test_get_comment_count(mock_client, make_request):
    """测试获取歌曲评论数量."""
    api = CommentApi(mock_client)
    biz_id = "003m8p9Z1v0T7b"

    await make_request(
        api.get_comment_count(biz_id),
        expected_module="music.globalComment.CommentCountSrv",
        expected_method="GetCmCount",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["request"]["biz_id"] == biz_id


@pytest.mark.anyio
async def test_get_hot_comments(mock_client, make_request):
    """测试获取歌曲热评."""
    api = CommentApi(mock_client)
    biz_id = "003m8p9Z1v0T7b"

    await make_request(
        api.get_hot_comments(biz_id, page_num=2),
        expected_module="music.globalComment.CommentRead",
        expected_method="GetHotCommentList",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["BizId"] == biz_id
    assert request_obj.param["PageNum"] == 1


@pytest.mark.anyio
async def test_get_new_comments(mock_client, make_request):
    """测试获取歌曲最新评论."""
    api = CommentApi(mock_client)
    biz_id = "003m8p9Z1v0T7b"

    await make_request(
        api.get_new_comments(biz_id, page_num=3),
        expected_module="music.globalComment.CommentRead",
        expected_method="GetNewCommentList",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["BizId"] == biz_id
    assert request_obj.param["PageNum"] == 2


@pytest.mark.anyio
async def test_get_recommend_comments(mock_client, make_request):
    """测试获取歌曲推荐评论."""
    api = CommentApi(mock_client)
    biz_id = "003m8p9Z1v0T7b"

    await make_request(
        api.get_recommend_comments(biz_id, page_num=1),
        expected_module="music.globalComment.CommentRead",
        expected_method="GetRecCommentList",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["BizId"] == biz_id
    assert request_obj.param["PageNum"] == 0


@pytest.mark.anyio
async def test_get_moment_comments(mock_client, make_request):
    """测试获取时刻评论."""
    api = CommentApi(mock_client)
    biz_id = "003m8p9Z1v0T7b"

    await make_request(
        api.get_moment_comments(biz_id),
        expected_module="music.globalComment.SongTsComment",
        expected_method="GetSongTsCmList",
    )

    args, _ = mock_client.execute.call_args
    request_obj = args[0]
    assert request_obj.param["BizId"] == biz_id
