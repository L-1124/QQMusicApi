"""评论 Web 路由契约."""

from qqmusic_api.models.comment import AddCommentResponse, CommentBizType
from qqmusic_api.modules.comment import CommentApi

from ..modules.comment import AddCommentBody
from ..routing.route_types import PUBLIC_60, AuthPolicy, HttpMethod, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(CommentApi.get_comment_count, "/song/{biz_id}/comments/count", cache=PUBLIC_60),
    R(CommentApi.get_hot_comments, "/song/{biz_id}/comments/hot", cache=PUBLIC_60),
    R(CommentApi.get_moment_comments, "/song/{biz_id}/comments/moments", cache=PUBLIC_60),
    R(CommentApi.get_new_comments, "/song/{biz_id}/comments/new", cache=PUBLIC_60),
    R(CommentApi.get_recommend_comments, "/song/{biz_id}/comments/recommended", cache=PUBLIC_60),
    R(
        "comment",
        "add_comment",
        "/song/{biz_id}/comments",
        AddCommentResponse,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        body_model=AddCommentBody,
        params=(
            P("biz_id", int, "业务 ID."),
            Q("biz_type", int | CommentBizType, CommentBizType.SONG, "业务类型."),
            Q("biz_sub_type", int | None, None, "业务子类型 (可选)."),
        ),
        summary="添加评论",
        description="为指定歌曲添加评论, 支持回复指定评论.",
    ),
    R(
        "comment",
        "delete_comment",
        "/comment/{cm_id}",
        bool,
        methods=(HttpMethod.DELETE,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        summary="删除评论",
        description="根据评论 ID 删除评论, 评论不存在也返回成功.",
    ),
)
