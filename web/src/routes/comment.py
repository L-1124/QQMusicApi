"""评论 Web 路由契约."""

from qqmusic_api.models.comment import AddCommentResponse
from qqmusic_api.modules.comment import CommentApi

from ..modules.comment import AddCommentBody
from ..routing.route_types import PUBLIC_60, AuthPolicy, HttpMethod, WebRoute
from ._helpers import BIZ_ID, COMMENT_BIZ_PARAMS, COMMENT_LIST_PAGE, COMMENT_MOMENT_PAGE, P, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        CommentApi.get_comment_count,
        "/song/{biz_id}/comments/count",
        params=(*BIZ_ID, *COMMENT_BIZ_PARAMS),
        cache=PUBLIC_60,
    ),
    R(
        CommentApi.get_hot_comments,
        "/song/{biz_id}/comments/hot",
        params=(*BIZ_ID, *COMMENT_LIST_PAGE, *COMMENT_BIZ_PARAMS),
        cache=PUBLIC_60,
    ),
    R(
        CommentApi.get_moment_comments,
        "/song/{biz_id}/comments/moments",
        params=(*BIZ_ID, *COMMENT_MOMENT_PAGE, *COMMENT_BIZ_PARAMS),
        cache=PUBLIC_60,
    ),
    R(
        CommentApi.get_new_comments,
        "/song/{biz_id}/comments/new",
        params=(*BIZ_ID, *COMMENT_LIST_PAGE, *COMMENT_BIZ_PARAMS),
        cache=PUBLIC_60,
    ),
    R(
        CommentApi.get_recommend_comments,
        "/song/{biz_id}/comments/recommended",
        params=(*BIZ_ID, *COMMENT_LIST_PAGE, *COMMENT_BIZ_PARAMS),
        cache=PUBLIC_60,
    ),
    R(
        "comment",
        "add_comment",
        "/song/{biz_id}/comments",
        AddCommentResponse,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        body_model=AddCommentBody,
        params=(*BIZ_ID, *COMMENT_BIZ_PARAMS),
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
        params=(P("cm_id", str, "评论 ID."),),
        summary="删除评论",
        description="根据评论 ID 删除评论, 评论不存在也返回成功.",
    ),
)
