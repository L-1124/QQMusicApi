"""评论模块."""

from ._base import ApiModule


class CommentApi(ApiModule):
    """评论 API."""

    def get_comment_count(self, biz_id: str):
        """获取歌曲评论数量.

        Args:
            biz_id: 业务 ID (通常为歌曲 ID).
        """
        data = {
            "request": {
                "biz_id": biz_id,
                "biz_type": 1,
                "biz_sub_type": 2,
            },
        }
        return self._build_request("music.globalComment.CommentCountSrv", "GetCmCount", data)

    def get_hot_comments(
        self,
        biz_id: str,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
    ):
        """获取业务热评.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
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
        return self._build_request("music.globalComment.CommentRead", "GetHotCommentList", params)

    def get_new_comments(
        self,
        biz_id: str,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
    ):
        """获取业务最新评论.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
        """
        params = {
            "PageSize": page_size,
            "PageNum": page_num - 1,
            "HashTagID": "",
            "BizType": 1,
            "PicEnable": 1,
            "LastCommentSeqNo": last_comment_seq_no,
            "SelfSeeEnable": 1,
            "BizId": biz_id,
            "AudioEnable": 1,
        }
        return self._build_request("music.globalComment.CommentRead", "GetNewCommentList", params)

    def get_recommend_comments(
        self,
        biz_id: str,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
    ):
        """获取业务推荐评论.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
        """
        params = {
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
        return self._build_request("music.globalComment.CommentRead", "GetRecCommentList", params)

    def get_moment_comments(
        self,
        biz_id: str,
        page_size: int = 15,
        last_comment_seq_no: str = "",
    ):
        """获取业务时刻评论.

        Args:
            biz_id: 业务 ID.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
        """
        params = {
            "LastPos": last_comment_seq_no,
            "HashTagID": "",
            "SeekTs": -1,
            "Size": page_size,
            "BizType": 1,
            "BizId": biz_id,
        }
        return self._build_request("music.globalComment.SongTsComment", "GetSongTsCmList", params)
