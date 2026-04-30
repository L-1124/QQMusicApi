"""自动生成的 Web 请求模型 — 请勿手动编辑此文件."""

from pydantic import Field

from .query_models import AutoPathModel, AutoQueryModel


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
