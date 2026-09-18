"""评论模块."""

from typing import Any

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import (
    CursorStrategy,
    MultiFieldContinuationStrategy,
    PaginationParams,
)
from ..models.comment import (
    AddCommentResponse,
    CommentBizType,
    CommentCountResponse,
    CommentItem,
    CommentListResponse,
    MomentCommentItem,
    MomentCommentResponse,
)
from ..models.request import Credential
from ._base import ApiModule


def _build_comment_pager_strategy() -> MultiFieldContinuationStrategy[CommentListResponse]:
    """构建评论列表接口使用的 continuation 策略."""

    def build_next_params(
        params: PaginationParams,
        response: CommentListResponse,
    ):
        if not response.has_more:
            return None
        cursor = response.comments[-1].seq_no if response.comments else None
        if cursor is None:
            return None
        next_params = params.copy()
        next_params["PageNum"] = next_params["PageNum"] + 1
        next_params["LastCommentSeqNo"] = cursor
        return next_params

    return MultiFieldContinuationStrategy[CommentListResponse](
        build_next_params,
        has_more_extractor=lambda r: bool(r.has_more),
        context_name="comment_list",
    )


class CommentApi(ApiModule):
    """评论 API."""

    @cgi_endpoint(
        key="comment.get_comment_count",
        module="music.globalComment.CommentCountSrv",
        method="GetCmCount",
        response_model=CommentCountResponse,
    )
    def get_comment_count(
        self,
        biz_id: int,
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
    ) -> CgiRequestData:
        """获取歌曲评论数量.

        Args:
            biz_id: 业务 ID.
            biz_type: 业务类型, 默认为普通歌曲.
            biz_sub_type: 业务子类型.
        """
        # 支持 request_list
        req_data: dict[str, Any] = {
            "biz_id": str(biz_id),
            "biz_type": int(biz_type),
        }
        if biz_sub_type is not None:
            req_data["biz_sub_type"] = biz_sub_type
        elif biz_type == CommentBizType.SONG:
            req_data["biz_sub_type"] = 2

        data = {"request": req_data}
        return CgiRequestData(param=data)

    @cgi_endpoint(
        key="comment.get_hot_comments",
        module="music.globalComment.CommentRead",
        method="GetHotCommentList",
        response_model=CommentListResponse,
        item_type=CommentItem,
    )
    def get_hot_comments(
        self,
        biz_id: int,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
    ) -> CgiRequestData:
        """获取歌曲热评.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
            biz_type: 业务类型.
            biz_sub_type: 业务子类型.
        """
        params: dict[str, Any] = {
            "BizType": int(biz_type),
            "BizId": str(biz_id),
            "LastCommentSeqNo": last_comment_seq_no,
            "PageSize": page_size,
            "PageNum": page_num - 1,
            "HotType": 1,
            "WithAirborne": 0,
            "PicEnable": 1,
        }
        if biz_sub_type is not None:
            params["BizSubType"] = biz_sub_type
        return CgiRequestData(
            param=params,
            pager_strategy=_build_comment_pager_strategy(),
            items_extractor=lambda r: r.comments,
        )

    @cgi_endpoint(
        key="comment.get_new_comments",
        module="music.globalComment.CommentRead",
        method="GetNewCommentList",
        response_model=CommentListResponse,
        item_type=CommentItem,
    )
    def get_new_comments(
        self,
        biz_id: int,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
    ) -> CgiRequestData:
        """获取歌曲最新评论.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
            biz_type: 业务类型.
            biz_sub_type: 业务子类型.
        """
        params: dict[str, Any] = {
            "PageSize": page_size,
            "PageNum": page_num - 1,
            "HashTagID": "",
            "BizType": int(biz_type),
            "PicEnable": 1,
            "LastCommentSeqNo": last_comment_seq_no,
            "SelfSeeEnable": 1,
            "BizId": str(biz_id),
            "AudioEnable": 1,
        }
        if biz_sub_type is not None:
            params["BizSubType"] = biz_sub_type
        return CgiRequestData(
            param=params,
            pager_strategy=_build_comment_pager_strategy(),
            items_extractor=lambda r: r.comments,
        )

    @cgi_endpoint(
        key="comment.get_recommend_comments",
        module="music.globalComment.CommentRead",
        method="GetRecCommentList",
        response_model=CommentListResponse,
        item_type=CommentItem,
    )
    def get_recommend_comments(
        self,
        biz_id: int,
        page_num: int = 1,
        page_size: int = 15,
        last_comment_seq_no: str = "",
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
    ) -> CgiRequestData:
        """获取歌曲推荐评论.

        Args:
            biz_id: 业务 ID.
            page_num: 页码.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
            biz_type: 业务类型.
            biz_sub_type: 业务子类型.
        """
        params: dict[str, Any] = {
            "PageSize": page_size,
            "PageNum": page_num - 1,
            "BizType": int(biz_type),
            "PicEnable": 1,
            "Flag": 1,
            "LastCommentSeqNo": last_comment_seq_no,
            "CmListUIVer": 1,
            "BizId": str(biz_id),
            "AudioEnable": 1,
        }
        if biz_sub_type is not None:
            params["BizSubType"] = biz_sub_type
        return CgiRequestData(
            param=params,
            pager_strategy=_build_comment_pager_strategy(),
            items_extractor=lambda r: r.comments,
        )

    @cgi_endpoint(
        key="comment.get_moment_comments",
        module="music.globalComment.SongTsComment",
        method="GetSongTsCmList",
        response_model=MomentCommentResponse,
        item_type=MomentCommentItem,
    )
    def get_moment_comments(
        self,
        biz_id: int,
        page_size: int = 15,
        last_comment_seq_no: str = "",
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
    ) -> CgiRequestData:
        """获取歌曲时刻评论.

        Args:
            biz_id: 业务 ID.
            page_size: 每页数量.
            last_comment_seq_no: 上一页最后一条评论 ID (可选).
            biz_type: 业务类型.
            biz_sub_type: 业务子类型.
        """
        params: dict[str, Any] = {
            "LastPos": last_comment_seq_no,
            "HashTagID": "",
            "SeekTs": -1,
            "Size": page_size,
            "BizType": int(biz_type),
            "BizId": str(biz_id),
        }
        if biz_sub_type is not None:
            params["BizSubType"] = biz_sub_type
        return CgiRequestData(
            param=params,
            pager_strategy=CursorStrategy[MomentCommentResponse](
                cursor_key="LastPos",
                has_more_extractor=lambda response: response.has_more == 1,
                cursor_extractor=lambda response: response.next_pos,
            ),
            items_extractor=lambda r: r.comments,
        )

    @cgi_endpoint(
        key="comment.add_comment",
        module="music.globalComment.CommentWriteServer",
        method="AddComment",
        response_model=AddCommentResponse,
        require_login=True,
    )
    def add_comment(
        self,
        biz_id: int,
        content: str,
        reply_cmt_id: str | None = None,
        biz_type: int | CommentBizType = CommentBizType.SONG,
        biz_sub_type: int | None = None,
        credential: Credential | None = None,
    ) -> CgiRequestData:
        """添加评论.

        Args:
            biz_id: 业务 ID.
            content: 评论内容.
            reply_cmt_id: 回复的评论 ID.
            biz_type: 业务类型.
            biz_sub_type: 业务子类型.
            credential: 登录凭据.
        """
        req_data: dict[str, Any] = {
            "Content": content,
            "BizType": int(biz_type),
            "BizId": str(biz_id),
        }
        if reply_cmt_id is not None:
            req_data["RepliedCmId"] = reply_cmt_id
        if biz_sub_type is not None:
            req_data["BizSubType"] = biz_sub_type

        return CgiRequestData(
            param=req_data,
            credential=credential,
        )

    async def delete_comment(
        self,
        cm_id: str,
        credential: Credential | None = None,
    ) -> bool:
        """删除评论.

        Args:
            cm_id: 评论 ID.
            credential: 登录凭据.

        Returns:
            是否删除成功,评论不存在也为 True.
        """
        data = await self._build_cgi(
            "music.globalComment.CommentWriteServer",
            "DelComment",
            {
                "CommentId": cm_id,
            },
            credential=credential,
            require_login=True,
        )
        return data.get("SubCode", 0) == 0
