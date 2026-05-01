"""评论 Web 路由契约."""

from qqmusic_api.models.comment import CommentCountResponse, CommentListResponse, MomentCommentResponse

from ..routing.route_types import PUBLIC_60, WebRoute
from ._helpers import BIZ_ID, COMMENT_LIST_PAGE, COMMENT_MOMENT_PAGE, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "comment",
        "get_comment_count",
        "/song/{biz_id}/comments/count",
        CommentCountResponse,
        params=BIZ_ID,
        cache=PUBLIC_60,
    ),
    R(
        "comment",
        "get_hot_comments",
        "/song/{biz_id}/comments/hot",
        CommentListResponse,
        params=(*BIZ_ID, *COMMENT_LIST_PAGE),
        cache=PUBLIC_60,
    ),
    R(
        "comment",
        "get_moment_comments",
        "/song/{biz_id}/comments/moments",
        MomentCommentResponse,
        params=(*BIZ_ID, *COMMENT_MOMENT_PAGE),
        cache=PUBLIC_60,
    ),
    R(
        "comment",
        "get_new_comments",
        "/song/{biz_id}/comments/new",
        CommentListResponse,
        params=(*BIZ_ID, *COMMENT_LIST_PAGE),
        cache=PUBLIC_60,
    ),
    R(
        "comment",
        "get_recommend_comments",
        "/song/{biz_id}/comments/recommended",
        CommentListResponse,
        params=(*BIZ_ID, *COMMENT_LIST_PAGE),
        cache=PUBLIC_60,
    ),
)
