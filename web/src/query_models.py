"""自动 Web 路由的显式 Query 参数模型."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType, TabType
from web.src.enum_utils import coerce_enum_value, enum_query_values


def _enum_schema(enum_type: Any) -> dict[str, Any]:
    """生成枚举 Query schema 扩展."""
    return {"enum": enum_query_values(enum_type)}


def _int_enum_value(value: int | str, enum_type: Any) -> int:
    """将 Web 枚举查询值转换为 modules 层整数值."""
    return int(coerce_enum_value(value, enum_type))


def _enum_value(value: str, enum_type: Any) -> Any:
    """将 Web 枚举查询值转换为 modules 层枚举成员."""
    return coerce_enum_value(value, enum_type)


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


class NoQuery(AutoQueryModel):
    """无 Query 参数."""


class ValueQuery(AutoQueryModel):
    """按 ID 或 MID 查询的通用 Query."""

    value: int | str = Field(description="资源 ID 或 MID.")


# BEGIN GENERATED WEB REQUEST MODELS
class ValuePath(AutoPathModel):
    """按 ID 或 MID 查询的通用 Path."""

    value: int | str = Field(description="资源 ID 或 MID.")


class SongIdPath(AutoPathModel):
    """歌曲 ID Path."""

    songid: int = Field(description="歌曲 ID.")


class MidPath(AutoPathModel):
    """MID Path."""

    mid: str = Field(description="资源 MID.")


class SonglistIdPath(AutoPathModel):
    """歌单 ID Path."""

    songlist_id: int = Field(description="歌单 ID.")


class TopIdPath(AutoPathModel):
    """排行榜 ID Path."""

    top_id: int = Field(description="排行榜 ID.")


class BizIdPath(AutoPathModel):
    """业务歌曲 ID Path."""

    biz_id: int = Field(description="业务歌曲 ID.")


class UinPath(AutoPathModel):
    """用户 UIN Path."""

    uin: int = Field(description="用户 UIN.")


class EuinPath(AutoPathModel):
    """加密用户 ID Path."""

    euin: str = Field(description="加密用户 ID.")


class AlbumSongPageQuery(AutoQueryModel):
    """专辑歌曲分页 Query."""

    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")


class CommentListPageQuery(AutoQueryModel):
    """评论列表分页 Query."""

    page_num: int = Field(default=1, description="页码.")
    page_size: int = Field(default=15, description="每页数量.")
    last_comment_seq_no: str = Field(default="", description="上一页最后一条评论序号.")


class CommentMomentPageQuery(AutoQueryModel):
    """弹幕评论分页 Query."""

    page_size: int = Field(default=15, description="每页数量.")
    last_comment_seq_no: str = Field(default="", description="上一页最后一条评论序号.")


class LyricOptionsQuery(AutoQueryModel):
    """歌词选项 Query."""

    qrc: bool = Field(default=False, description="是否返回逐字歌词.")
    trans: bool = Field(default=False, description="是否返回翻译歌词.")
    roma: bool = Field(default=False, description="是否返回罗马音歌词.")


class SingerPageQuery(AutoQueryModel):
    """歌手资源分页 Query."""

    number: int = Field(default=10, description="返回数量.")
    begin: int = Field(default=0, description="分页起始位置.")


class SingerSimilarPageQuery(AutoQueryModel):
    """相似歌手分页 Query."""

    number: int = Field(default=10, description="返回数量.")


class SingerTabPageQuery(AutoQueryModel):
    """歌手主页 Tab 分页 Query."""

    page: int = Field(default=1, description="页码.")
    num: int = Field(default=10, description="返回数量.")


class SongRelatedMvPageQuery(AutoQueryModel):
    """歌曲相关 MV 分页 Query."""

    last_mvid: str | None = Field(default=None, description="上一页最后一个 MV ID.")


class SongRelatedSonglistPageQuery(AutoQueryModel):
    """歌曲相关歌单分页 Query."""

    last: list[int] | None = Field(default=None, description="上一页游标.")


class SonglistDetailOptionsQuery(AutoQueryModel):
    """歌单详情选项 Query."""

    dirid: int = Field(default=0, description="目录 ID.")
    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")
    onlysong: bool = Field(default=False, description="是否仅返回歌曲.")
    tag: bool = Field(default=True, description="是否返回标签.")
    userinfo: bool = Field(default=True, description="是否返回用户信息.")


class TopDetailOptionsQuery(AutoQueryModel):
    """排行榜详情选项 Query."""

    num: int = Field(default=10, description="返回数量.")
    page: int = Field(default=1, description="页码.")
    tag: bool = Field(default=True, description="是否返回标签.")


class UserPageQuery(AutoQueryModel):
    """当前用户分页列表 Query."""

    page: int = Field(default=1, description="页码.")
    num: int = Field(default=10, description="返回数量.")


# END GENERATED WEB REQUEST MODELS


class SingerTabPath(MidPath):
    """歌手主页 Tab Path."""

    tab_type: str = Field(
        description="Tab 类型.",
        json_schema_extra=_enum_schema(TabType),
    )

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换 Tab 类型为 modules 层枚举成员."""
        kwargs = super().to_method_kwargs()
        kwargs["tab_type"] = _enum_value(self.tab_type, TabType)
        return kwargs


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

    search_type: int | str = Field(
        default=SearchType.SONG.name,
        description="搜索类型.",
        json_schema_extra=_enum_schema(SearchType),
    )
    num: int = Field(default=10, description="返回数量.")

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换搜索类型为 modules 层整数值."""
        kwargs = super().to_method_kwargs()
        kwargs["search_type"] = _int_enum_value(self.search_type, SearchType)
        return kwargs


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

    enum_fields: ClassVar[dict[str, Any]] = {
        "area": AreaType,
        "sex": SexType,
        "genre": GenreType,
    }

    area: int | str = Field(
        default=AreaType.ALL.name,
        description="地区类型.",
        json_schema_extra=_enum_schema(AreaType),
    )
    sex: int | str = Field(
        default=SexType.ALL.name,
        description="性别类型.",
        json_schema_extra=_enum_schema(SexType),
    )
    genre: int | str = Field(
        default=GenreType.ALL.name,
        description="风格类型.",
        json_schema_extra=_enum_schema(GenreType),
    )

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换歌手分类枚举为 modules 层整数值."""
        kwargs = super().to_method_kwargs()
        for field_name, enum_type in self.enum_fields.items():
            kwargs[field_name] = _int_enum_value(kwargs[field_name], enum_type)
        return kwargs


class SingerIndexQuery(SingerTypeQuery):
    """歌手索引分页 Query."""

    enum_fields: ClassVar[dict[str, Any]] = {
        **SingerTypeQuery.enum_fields,
        "index": IndexType,
    }

    index: int | str = Field(
        default=IndexType.ALL.name,
        description="首字母索引.",
        json_schema_extra=_enum_schema(IndexType),
    )
    sin: int = Field(default=0, description="起始位置.")
    cur_page: int = Field(default=1, description="当前页码.")


class SingerTabDetailQuery(SingerMidQuery):
    """歌手主页 Tab Query."""

    tab_type: str = Field(
        description="Tab 类型.",
        json_schema_extra=_enum_schema(TabType),
    )
    page: int = Field(default=1, description="页码.")
    num: int = Field(default=10, description="返回数量.")

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换 Tab 类型为 modules 层枚举成员."""
        kwargs = super().to_method_kwargs()
        kwargs["tab_type"] = _enum_value(self.tab_type, TabType)
        return kwargs


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
