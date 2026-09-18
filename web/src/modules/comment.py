"""评论模块 Web 路由适配."""

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from qqmusic_api.modules.comment import CommentApi

from ..routing.adapter_registry import adapter
from ..routing.route_types import RouteContext


class AddCommentBody(BaseModel):
    """添加评论请求体."""

    content: str = Field(description="评论内容.")
    reply_cmt_id: str | SkipJsonSchema[None] = Field(default=None, description="回复的评论 ID.")


@adapter("comment", "add_comment")
async def add_comment_adapter(context: RouteContext):
    """添加评论适配器."""
    body: AddCommentBody = context.params["body"]
    return await context.execute_module(
        CommentApi,
        CommentApi.add_comment,
        biz_id=context.params["biz_id"],
        content=body.content,
        reply_cmt_id=body.reply_cmt_id,
        biz_type=context.params.get("biz_type", 1),
        biz_sub_type=context.params.get("biz_sub_type"),
        credential=context.credential,
    )
