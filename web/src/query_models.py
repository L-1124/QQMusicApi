"""自动 Web 路由的显式 Query 参数模型."""

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType, TabType
from web.src.enum_utils import flexible_enum_validator


class AutoRequestModel(BaseModel):
    """自动路由请求参数基类."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换为 modules 方法参数."""
        return self.model_dump()


class AutoQueryModel(AutoRequestModel):
    """自动路由 Query 参数基类."""


class AutoPathModel(AutoRequestModel):
    """自动路由 Path 参数基类."""


class AutoBodyModel(AutoRequestModel):
    """自动路由 Body 参数基类 (Pydantic 模型 -> FastAPI 自动识别为 Request Body)."""


class NoQuery(AutoQueryModel):
    """无 Query 参数."""


class ValueQuery(AutoQueryModel):
    """按 ID 或 MID 查询的通用 Query."""

    value: int | str = Field(description="资源 ID 或 MID.")


from web.src._generated_models import *  # noqa: E402, F403

# BEGIN GENERATED WEB REQUEST MODELS (see _generated_models.py)
# END GENERATED WEB REQUEST MODELS


class SingerTabPath(MidPath):  # noqa: F405
    """歌手主页 Tab Path."""

    tab_type: Annotated[TabType, BeforeValidator(flexible_enum_validator(TabType))] = Field(description="Tab 类型.")


class AlbumGetSongQuery(ValueQuery):
    """专辑歌曲列表 Query."""

    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")


class CommentCountQuery(AutoQueryModel):
    """评论数量 Query."""

    biz_id: int = Field(description="业务 ID.")


class CommentListQuery(CommentCountQuery):
    """评论列表 Query."""

    page_num: int = Field(default=1, description="页码.")
    page_size: int = Field(default=15, description="每页数量.")
    last_comment_seq_no: str = Field(default="", description="上一页最后一条评论序号.")


class CommentMomentQuery(CommentCountQuery):
    """弹幕评论 Query."""

    page_size: int = Field(default=15, description="每页数量.")
    last_comment_seq_no: str = Field(default="", description="上一页最后一条评论序号.")


class LyricGetLyricQuery(ValueQuery):
    """歌词 Query."""

    qrc: bool = Field(default=False, description="是否返回逐字歌词.")
    trans: bool = Field(default=False, description="是否返回翻译歌词.")
    roma: bool = Field(default=False, description="是否返回罗马音歌词.")


class MvGetDetailQuery(AutoQueryModel):
    """MV 详情 Query."""

    vids: list[str] = Field(description="MV VID 列表.")


class PageQuery(AutoQueryModel):
    """页码 Query."""

    page: int = Field(default=1, description="页码.")


class KeywordQuery(AutoQueryModel):
    """关键词 Query."""

    keyword: str = Field(description="关键词.")


class SearchGeneralQuery(KeywordQuery):
    """综合搜索 Query."""

    page: int = Field(default=1, description="页码.")
    highlight: bool = Field(default=True, description="是否高亮关键词.")


class SearchByTypeQuery(SearchGeneralQuery):
    """分类搜索 Query."""

    search_type: Annotated[SearchType, BeforeValidator(flexible_enum_validator(SearchType))] = Field(
        default=SearchType.SONG,
        description="搜索类型.",
    )
    num: int = Field(default=10, description="返回数量.")


class SingerMidQuery(AutoQueryModel):
    """歌手 MID Query."""

    mid: str = Field(description="歌手 MID.")


class SingerPagedMidQuery(SingerMidQuery):
    """歌手分页资源 Query."""

    number: int = Field(default=10, description="返回数量.")
    begin: int = Field(default=0, description="分页起始位置.")


class SingerDescQuery(AutoQueryModel):
    """歌手描述 Query."""

    mids: list[str] = Field(description="歌手 MID 列表.")


class SingerSimilarQuery(SingerMidQuery):
    """相似歌手 Query."""

    number: int = Field(default=10, description="返回数量.")


class SingerTypeQuery(AutoQueryModel):
    """歌手分类 Query."""

    area: Annotated[AreaType, BeforeValidator(flexible_enum_validator(AreaType))] = Field(
        default=AreaType.ALL,
        description="地区类型.",
    )
    sex: Annotated[SexType, BeforeValidator(flexible_enum_validator(SexType))] = Field(
        default=SexType.ALL,
        description="性别类型.",
    )
    genre: Annotated[GenreType, BeforeValidator(flexible_enum_validator(GenreType))] = Field(
        default=GenreType.ALL,
        description="风格类型.",
    )


class SingerIndexQuery(SingerTypeQuery):
    """歌手索引分页 Query."""

    index: Annotated[IndexType, BeforeValidator(flexible_enum_validator(IndexType))] = Field(
        default=IndexType.ALL,
        description="首字母索引.",
    )
    sin: int = Field(default=0, description="起始位置.")
    cur_page: int = Field(default=1, description="当前页码.")


class SingerTabDetailQuery(SingerMidQuery):
    """歌手主页 Tab Query."""

    tab_type: Annotated[TabType, BeforeValidator(flexible_enum_validator(TabType))] = Field(description="Tab 类型.")
    page: int = Field(default=1, description="页码.")
    num: int = Field(default=10, description="返回数量.")


class SongIdsQuery(AutoQueryModel):
    """歌曲 ID 列表 Query."""

    song_ids: list[int] = Field(description="歌曲 ID 列表.")


class SongIdQuery(AutoQueryModel):
    """歌曲 ID Query."""

    songid: int = Field(description="歌曲 ID.")


class SongRelatedMvQuery(SongIdQuery):
    """歌曲相关 MV Query."""

    last_mvid: str | None = Field(default=None, description="上一页最后一个 MV ID.")


class SongRelatedSonglistQuery(SongIdQuery):
    """歌曲相关歌单 Query."""

    last: list[int] | None = Field(default=None, description="上一页游标.")


class SongSheetQuery(AutoQueryModel):
    """歌单页歌曲 Query."""

    mid: str = Field(description="歌曲 MID.")


class SonglistCreateQuery(AutoQueryModel):
    """创建歌单 Query."""

    dirname: str = Field(description="歌单名称.")


class SonglistDeleteQuery(AutoQueryModel):
    """删除歌单 Query."""

    dirid: int = Field(description="歌单目录 ID.")


class SonglistGetDetailQuery(AutoQueryModel):
    """歌单详情 Query."""

    songlist_id: int = Field(description="歌单 ID.")
    dirid: int = Field(default=0, description="目录 ID.")
    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")
    onlysong: bool = Field(default=False, description="是否仅返回歌曲.")
    tag: bool = Field(default=True, description="是否返回标签.")
    userinfo: bool = Field(default=True, description="是否返回用户信息.")


class TopGetDetailQuery(AutoQueryModel):
    """排行榜详情 Query."""

    top_id: int = Field(description="排行榜 ID.")
    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")
    tag: bool = Field(default=True, description="是否返回标签.")


class UserUinQuery(AutoQueryModel):
    """用户 UIN Query."""

    uin: int = Field(description="用户 UIN.")


class UserEuinQuery(AutoQueryModel):
    """加密用户 ID Query."""

    euin: str = Field(description="加密用户 ID.")


class UserPagedEuinQuery(UserEuinQuery):
    """用户分页列表 Query."""

    page: int = Field(default=1, description="页码.")
    num: int = Field(default=10, description="返回数量.")
