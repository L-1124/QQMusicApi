"""评论 API"""

from .utils.network import NO_PROCESSOR, api_request


@api_request("music.globalComment.CommentCountSrv", "GetCmCount")
async def get_comment_count(biz_id: str):
    """获取歌曲评论数量

    Args:
        biz_id: 歌曲 ID
    """
    return {
        "request": {
            "biz_id": biz_id,
            "biz_type": 1,
            "biz_sub_type": 2,
        },
    }, NO_PROCESSOR


@api_request("music.globalComment.CommentRead", "GetHotCommentList")
async def get_hot_comments(
    biz_id: str,
    page_num: int = 1,
    page_size: int = 15,
    last_comment_seq_no: str = "",
):
    """获取歌曲热评

    Args:
        biz_id: 歌曲 ID
        page_num: 页码
        page_size: 每页数量
        last_comment_seq_no: 上一页最后一条评论 ID(可选)
    """
    params = {
        "BizType": 1,
        "BizId": biz_id,
        "LastCommentSeqNo": last_comment_seq_no,
        "PageSize": page_size,
        "PageNum": page_num - 1,
        "HotType": 1,
        "WithAirborne": 0,
        "PicEnable": 1,
    }

    return params, NO_PROCESSOR


@api_request("music.globalComment.CommentRead", "GetNewCommentList")
async def get_new_comments(
    biz_id: str,
    page_num: int = 1,
    page_size: int = 15,
    last_comment_seq_no: str = "",
):
    """获取歌曲最新评论

    Args:
        biz_id: 歌曲 ID
        page_num: 页码
        page_size: 每页数量
        last_comment_seq_no: 上一页最后一条评论 ID(可选)
    """
    params = {
        # "LastRspVer": "",
        # "LastTotalVer": "1755832873618224522",
        "PageSize": page_size,
        "PageNum": page_num - 1,
        "HashTagID": "",
        "BizType": 1,
        # "LastCommentId": "",
        "PicEnable": 1,
        "LastCommentSeqNo": last_comment_seq_no,
        "SelfSeeEnable": 1,
        # "LastTotal": 325,
        # "CmListUIVer": 1,
        "BizId": biz_id,
        "AudioEnable": 1,
    }

    return params, NO_PROCESSOR


@api_request("music.globalComment.CommentRead", "GetRecCommentList")
async def get_recommend_comments(
    biz_id: str,
    page_num: int = 1,
    page_size: int = 15,
    last_comment_seq_no: str = "",
):
    """获取歌曲推荐评论

    Args:
        biz_id: 歌曲 ID
        page_num: 页码
        page_size: 每页数量
        last_comment_seq_no: 上一页最后一条评论 ID(可选)
    """
    params = {
        # "FromParentCmId": "",
        # "LastRspVer": "1755834843787200911",
        # "LastTotalVer": "1755834843679664122",
        # "RecOffset": 0,
        # "LastHotScore": "",
        # "FromCommentId": "",
        # "HashTagID": "",
        # "CommentIds": [],
        # "LastRecScore": "",
        # "LastTotal": 325,
        "PageSize": page_size,
        "PageNum": page_num - 1,
        "BizType": 1,
        "PicEnable": 1,
        "Flag": 1,
        "LastCommentSeqNo": last_comment_seq_no,
        "CmListUIVer": 1,
        "BizId": biz_id,
        "AudioEnable": 1,
    }

    return params, NO_PROCESSOR


@api_request("music.globalComment.SongTsComment", "GetSongTsCmList")
async def get_moment_comments(
    biz_id: str,
    page_size: int = 15,
    last_comment_seq_no: str = "",
):
    """获取时刻评论

    Args:
        biz_id: 歌曲 ID
        page_size: 每页数量
        last_comment_seq_no: 上一页最后一条评论ID
    """
    params = {
        "LastPos": last_comment_seq_no,
        "HashTagID": "",
        "SeekTs": -1,
        "Size": page_size,
        "BizType": 1,
        "BizId": biz_id,
    }
    return params, NO_PROCESSOR
