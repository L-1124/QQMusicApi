"""Web 路由声明辅助函数与共享参数."""

from typing import Any

from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType

from ..routing.route_types import (
    AuthPolicy,
    EnumIntMapping,
    HttpMethod,
    ParamOverride,
    ParamSource,
    WebRoute,
)


def Q(
    name: str,
    annotation: Any,
    default: Any = ...,
    description: str | None = None,
    *,
    enum_mapping: EnumIntMapping[Any] | None = None,
) -> ParamOverride:
    """声明 Query 参数."""
    return ParamOverride(
        name=name,
        source=ParamSource.QUERY,
        default=default,
        annotation=annotation,
        description=description,
        enum_mapping=enum_mapping,
    )


def P(name: str, annotation: Any, description: str | None = None) -> ParamOverride:
    """声明 Path 参数."""
    return ParamOverride(name=name, source=ParamSource.PATH, annotation=annotation, description=description)


def R(
    module: str,
    method: str,
    path: str,
    response_model: Any,
    *,
    params: tuple[ParamOverride, ...] = (),
    methods: tuple[HttpMethod, ...] = (HttpMethod.GET,),
    auth: AuthPolicy = AuthPolicy.NONE,
    cache: Any = None,
    adapter: Any = None,
    body_model: Any = None,
    summary: str | None = None,
    description: str | None = None,
) -> WebRoute:
    """声明 Web 路由."""
    return WebRoute(
        module=module,
        method=method,
        path=path,
        methods=methods,
        response_model=response_model,
        param_overrides=params,
        auth=auth,
        cache=cache,
        adapter=adapter,
        body_model=body_model,
        summary=summary,
        description=description,
    )


VALUE = (P("value", int | str, "资源 ID 或 MID."),)
MID = (P("mid", str, "资源 MID."),)
SONG_ID = (P("songid", int, "歌曲 ID."),)
BIZ_ID = (P("biz_id", int, "业务歌曲 ID."),)
SONGLIST_ID = (P("songlist_id", int, "歌单 ID."),)
TOP_ID = (P("top_id", int, "排行榜 ID."),)
UIN = (P("uin", int, "用户 UIN."),)
EUIN = (P("euin", str, "加密用户 ID."),)
ALBUM_PAGE = (Q("num", int, 10, "返回数量."), Q("page", int, 1, "页码."))
COMMENT_LIST_PAGE = (
    Q("page_num", int, 1, "页码."),
    Q("page_size", int, 15, "每页数量."),
    Q("last_comment_seq_no", str, "", "上一页最后一条评论序号."),
)
COMMENT_MOMENT_PAGE = (
    Q("page_size", int, 15, "每页数量."),
    Q("last_comment_seq_no", str, "", "上一页最后一条评论序号."),
)
LYRIC_OPTIONS = (
    Q("qrc", bool, default=False, description="是否返回逐字歌词."),
    Q("trans", bool, default=False, description="是否返回翻译歌词."),
    Q("roma", bool, default=False, description="是否返回罗马音歌词."),
)
SINGER_PAGE = (Q("num", int, 10, "返回数量."), Q("page", int, 1, "页码."))
SINGER_SIMILAR_PAGE = (Q("number", int, 10, "返回数量."),)
SINGER_TAB_PAGE = (Q("page", int, 1, "页码."), Q("num", int, 10, "返回数量."))
SINGER_TYPE = (
    Q("area", AreaType, AreaType.ALL, "地区类型."),
    Q("sex", SexType, SexType.ALL, "性别类型."),
    Q("genre", GenreType, GenreType.ALL, "风格类型."),
)
SINGER_INDEX = (
    *SINGER_TYPE,
    Q("index", IndexType, IndexType.ALL, "首字母索引."),
    Q("num", int, 80, "每页返回数量."),
    Q("page", int, 1, "页码."),
)
SONG_RELATED_MV_PAGE = (Q("last_mvid", str | None, None, "上一页最后一个 MV ID."),)
SONG_RELATED_SONGLIST_PAGE = (Q("last", list[int] | None, None, "上一页游标."),)
SONGLIST_DETAIL_OPTIONS = (
    Q("dirid", int, 0, "目录 ID."),
    Q("num", int, 10, "返回数量."),
    Q("page", int, 1, "页码."),
    Q("onlysong", bool, default=False, description="是否仅返回歌曲."),
    Q("tag", bool, default=True, description="是否返回标签."),
    Q("userinfo", bool, default=True, description="是否返回用户信息."),
)
TOP_DETAIL_OPTIONS = (
    Q("num", int, 10, "返回数量."),
    Q("page", int, 1, "页码."),
    Q("tag", bool, default=True, description="是否返回标签."),
)
USER_PAGE = (Q("page", int, 1, "页码."), Q("num", int, 10, "返回数量."))
KEYWORD = (Q("keyword", str, description="关键词."),)
SEARCH_GENERAL = (
    *KEYWORD,
    Q("page", int, 1, "页码."),
    Q("highlight", bool, default=True, description="是否高亮关键词."),
)
SEARCH_BY_TYPE = (
    *SEARCH_GENERAL,
    Q("search_type", SearchType, SearchType.SONG, "搜索类型."),
    Q("num", int, 10, "返回数量."),
)
