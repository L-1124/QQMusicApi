"""排行榜模型."""

from typing import Any

from pydantic import BaseModel, Field


class TopCategory(BaseModel):
    """排行榜分类."""

    group_id: int = Field(alias="groupId")
    group_name: str = Field(alias="groupName")
    toplist: list[dict[str, Any]]


class TopCategoryResponse(BaseModel):
    """排行榜分类响应."""

    group: list[TopCategory]
