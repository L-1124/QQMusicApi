"""自动生成的路由模型契约 — 请勿手动编辑此文件."""

from .route_manifest import FieldContract, RequestModelContract

REQUEST_MODEL_CONTRACTS: tuple[RequestModelContract, ...] = (
    RequestModelContract(
        name="ValuePath",
        base="AutoPathModel",
        docstring="按 ID 或 MID 查询的通用 Path.",
        fields=(
            FieldContract(
                name="value",
                annotation="int | str",
                default=None,
                description="资源 ID 或 MID.",
            ),
        ),
    ),
    RequestModelContract(
        name="SongIdPath",
        base="AutoPathModel",
        docstring="歌曲 ID Path.",
        fields=(
            FieldContract(
                name="songid",
                annotation="int",
                default=None,
                description="歌曲 ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="MidPath",
        base="AutoPathModel",
        docstring="MID Path.",
        fields=(
            FieldContract(
                name="mid",
                annotation="str",
                default=None,
                description="资源 MID.",
            ),
        ),
    ),
    RequestModelContract(
        name="SonglistIdPath",
        base="AutoPathModel",
        docstring="歌单 ID Path.",
        fields=(
            FieldContract(
                name="songlist_id",
                annotation="int",
                default=None,
                description="歌单 ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="TopIdPath",
        base="AutoPathModel",
        docstring="排行榜 ID Path.",
        fields=(
            FieldContract(
                name="top_id",
                annotation="int",
                default=None,
                description="排行榜 ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="BizIdPath",
        base="AutoPathModel",
        docstring="业务歌曲 ID Path.",
        fields=(
            FieldContract(
                name="biz_id",
                annotation="int",
                default=None,
                description="业务歌曲 ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="UinPath",
        base="AutoPathModel",
        docstring="用户 UIN Path.",
        fields=(
            FieldContract(
                name="uin",
                annotation="int",
                default=None,
                description="用户 UIN.",
            ),
        ),
    ),
    RequestModelContract(
        name="EuinPath",
        base="AutoPathModel",
        docstring="加密用户 ID Path.",
        fields=(
            FieldContract(
                name="euin",
                annotation="str",
                default=None,
                description="加密用户 ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="AlbumSongPageQuery",
        base="AutoQueryModel",
        docstring="专辑歌曲分页 Query.",
        fields=(
            FieldContract(
                name="num",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
            FieldContract(
                name="page",
                annotation="int",
                default="1",
                description="页码.",
            ),
        ),
    ),
    RequestModelContract(
        name="CommentListPageQuery",
        base="AutoQueryModel",
        docstring="评论列表分页 Query.",
        fields=(
            FieldContract(
                name="page_num",
                annotation="int",
                default="1",
                description="页码.",
            ),
            FieldContract(
                name="page_size",
                annotation="int",
                default="15",
                description="每页数量.",
            ),
            FieldContract(
                name="last_comment_seq_no",
                annotation="str",
                default='""',
                description="上一页最后一条评论序号.",
            ),
        ),
    ),
    RequestModelContract(
        name="CommentMomentPageQuery",
        base="AutoQueryModel",
        docstring="弹幕评论分页 Query.",
        fields=(
            FieldContract(
                name="page_size",
                annotation="int",
                default="15",
                description="每页数量.",
            ),
            FieldContract(
                name="last_comment_seq_no",
                annotation="str",
                default='""',
                description="上一页最后一条评论序号.",
            ),
        ),
    ),
    RequestModelContract(
        name="LyricOptionsQuery",
        base="AutoQueryModel",
        docstring="歌词选项 Query.",
        fields=(
            FieldContract(
                name="qrc",
                annotation="bool",
                default="False",
                description="是否返回逐字歌词.",
            ),
            FieldContract(
                name="trans",
                annotation="bool",
                default="False",
                description="是否返回翻译歌词.",
            ),
            FieldContract(
                name="roma",
                annotation="bool",
                default="False",
                description="是否返回罗马音歌词.",
            ),
        ),
    ),
    RequestModelContract(
        name="SingerPageQuery",
        base="AutoQueryModel",
        docstring="歌手资源分页 Query.",
        fields=(
            FieldContract(
                name="number",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
            FieldContract(
                name="begin",
                annotation="int",
                default="0",
                description="分页起始位置.",
            ),
        ),
    ),
    RequestModelContract(
        name="SingerSimilarPageQuery",
        base="AutoQueryModel",
        docstring="相似歌手分页 Query.",
        fields=(
            FieldContract(
                name="number",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
        ),
    ),
    RequestModelContract(
        name="SingerTabPageQuery",
        base="AutoQueryModel",
        docstring="歌手主页 Tab 分页 Query.",
        fields=(
            FieldContract(
                name="page",
                annotation="int",
                default="1",
                description="页码.",
            ),
            FieldContract(
                name="num",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
        ),
    ),
    RequestModelContract(
        name="SongRelatedMvPageQuery",
        base="AutoQueryModel",
        docstring="歌曲相关 MV 分页 Query.",
        fields=(
            FieldContract(
                name="last_mvid",
                annotation="str | None",
                default="None",
                description="上一页最后一个 MV ID.",
            ),
        ),
    ),
    RequestModelContract(
        name="SongRelatedSonglistPageQuery",
        base="AutoQueryModel",
        docstring="歌曲相关歌单分页 Query.",
        fields=(
            FieldContract(
                name="last",
                annotation="list[int] | None",
                default="None",
                description="上一页游标.",
            ),
        ),
    ),
    RequestModelContract(
        name="SonglistDetailOptionsQuery",
        base="AutoQueryModel",
        docstring="歌单详情选项 Query.",
        fields=(
            FieldContract(
                name="dirid",
                annotation="int",
                default="0",
                description="目录 ID.",
            ),
            FieldContract(
                name="num",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
            FieldContract(
                name="page",
                annotation="int",
                default="1",
                description="页码.",
            ),
            FieldContract(
                name="onlysong",
                annotation="bool",
                default="False",
                description="是否仅返回歌曲.",
            ),
            FieldContract(
                name="tag",
                annotation="bool",
                default="True",
                description="是否返回标签.",
            ),
            FieldContract(
                name="userinfo",
                annotation="bool",
                default="True",
                description="是否返回用户信息.",
            ),
        ),
    ),
    RequestModelContract(
        name="TopDetailOptionsQuery",
        base="AutoQueryModel",
        docstring="排行榜详情选项 Query.",
        fields=(
            FieldContract(
                name="num",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
            FieldContract(
                name="page",
                annotation="int",
                default="1",
                description="页码.",
            ),
            FieldContract(
                name="tag",
                annotation="bool",
                default="True",
                description="是否返回标签.",
            ),
        ),
    ),
    RequestModelContract(
        name="UserPageQuery",
        base="AutoQueryModel",
        docstring="当前用户分页列表 Query.",
        fields=(
            FieldContract(
                name="page",
                annotation="int",
                default="1",
                description="页码.",
            ),
            FieldContract(
                name="num",
                annotation="int",
                default="10",
                description="返回数量.",
            ),
        ),
    ),
)
