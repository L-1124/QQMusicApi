"""Comment API 返回模型定义."""

from typing import Any

from pydantic import Field

from .request import Response


class IconTextInfo(Response):
    """评论数量接口附带的角标文案与展示标识.

    Attributes:
        txt: 角标展示文案.
        unique_id: 角标唯一标识.
        type: 角标类型.
        cmid: 关联评论 ID.
        is_dynamic: 是否为动态角标.
    """

    txt: str
    unique_id: str
    type: int
    cmid: str
    is_dynamic: bool


class CommentCountResponse(Response):
    """评论数量接口整理后的统计结果.

    Attributes:
        biz_type: 业务类型.
        biz_id: 业务对象 ID.
        biz_sub_type: 业务子类型.
        count: 评论总数.
        count_ver: 计数字段版本.
        count_view: 面向展示的计数文案.
        related_id: 关联对象 ID.
        tip: 附加提示文案.
        icon_list: 角标信息列表.
        cm_tab_type: 评论标签页类型.
    """

    biz_type: int = Field(json_schema_extra={"jsonpath": "$.response.biz_type"})
    biz_id: str = Field(json_schema_extra={"jsonpath": "$.response.biz_id"})
    biz_sub_type: int = Field(json_schema_extra={"jsonpath": "$.response.biz_sub_type"})
    count: int = Field(json_schema_extra={"jsonpath": "$.response.count"})
    count_ver: str = Field(json_schema_extra={"jsonpath": "$.response.count_ver"})
    count_view: str = Field(json_schema_extra={"jsonpath": "$.response.count_view"})
    related_id: str = Field(json_schema_extra={"jsonpath": "$.response.related_id"})
    tip: str = Field(json_schema_extra={"jsonpath": "$.response.tip"})
    icon_list: list[IconTextInfo] = Field(
        default_factory=list,
        json_schema_extra={"jsonpath": "$.response.icon_list[*]"},
    )
    cm_tab_type: int = Field(json_schema_extra={"jsonpath": "$.cmTabType"})


class CommentItem(Response):
    """标准评论列表中的单条评论记录.

    Attributes:
        cmid: 评论 ID.
        seq_no: 评论序号.
        nick: 昵称.
        avatar: 头像地址.
        encrypt_uin: 加密 UIN.
        content: 评论正文.
        pub_time: 发布时间戳.
        praise_num: 点赞数.
        reply_cnt: 回复数.
        is_praised: 当前账号是否已点赞.
        is_self: 是否为本人评论.
        state: 评论状态.
        hot_score: 热度分数文案.
        rec_score: 推荐分数文案.
        song_id: 关联歌曲 ID.
        song_name: 关联歌曲名.
        singer_names: 关联歌手名串.
        song_ts_elems: 歌曲时间轴元素.
        hash_tag_list: 话题标签列表.
        little_tails: 尾巴挂件列表.
        icon_list: 图标列表.
        vip_ui: VIP 展示信息.
        sub_comments: 子评论列表.
    """

    cmid: str = Field(alias="CmId")
    seq_no: str = Field(alias="SeqNo")
    nick: str = Field(alias="Nick")
    avatar: str = Field(alias="Avatar")
    encrypt_uin: str = Field(alias="EncryptUin")
    content: str = Field(alias="Content")
    pub_time: int = Field(alias="PubTime")
    praise_num: int = Field(alias="PraiseNum")
    reply_cnt: int = Field(alias="ReplyCnt")
    is_praised: int = Field(alias="IsPraised")
    is_self: int = Field(alias="IsSelf")
    state: int = Field(alias="State")
    hot_score: str = Field(alias="HotScore")
    rec_score: str = Field(alias="RecScore")
    song_id: int = Field(alias="SongId")
    song_name: str = Field(alias="SongName")
    singer_names: str = Field(alias="SingerNames")
    song_ts_elems: list[dict[str, Any]] = Field(default_factory=list, alias="SongTsElems")
    hash_tag_list: list[dict[str, Any]] = Field(default_factory=list, alias="HashTagList")
    little_tails: list[dict[str, Any]] = Field(default_factory=list, alias="LittleTails")
    icon_list: list[dict[str, Any]] = Field(default_factory=list, alias="IconList")
    vip_ui: dict[str, Any] = Field(default_factory=dict, alias="VipUI")
    sub_comments: list[dict[str, Any]] = Field(default_factory=list, alias="SubComments")


class CommentListResponse(Response):
    """歌曲等常规内容评论列表接口的响应体.

    Attributes:
        comments: 当前页评论列表.
        comment_ids: 当前页评论 ID 列表.
        has_more: 是否还有更多结果.
        next_offset: 下一页偏移量.
        total: 评论总数.
        total_cm_num: 评论总量字段.
        comment_tip: 评论提示文案.
        comment_h5_page: H5 页面地址.
        has_ts_cm: 是否包含时间轴评论.
        share_cnt: 分享数.
        msg: 附加消息.
        subcode: 子返回码.
    """

    comments: list[CommentItem] = Field(
        default_factory=list,
        json_schema_extra={"jsonpath": "$.CommentList.Comments[*]"},
    )
    comment_ids: list[str] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.CommentList.CommentIds[*]"})
    has_more: int = Field(json_schema_extra={"jsonpath": "$.CommentList.HasMore"})
    next_offset: int = Field(json_schema_extra={"jsonpath": "$.CommentList.NextOffset"})
    total: int = Field(json_schema_extra={"jsonpath": "$.CommentList.Total"})
    total_cm_num: int = Field(alias="TotalCmNum")
    comment_tip: str = Field(alias="CommentTip")
    comment_h5_page: str = Field(alias="CommentH5Page")
    has_ts_cm: int = Field(alias="HasTsCm")
    share_cnt: int = Field(alias="ShareCnt")
    msg: str = Field(alias="Msg")
    subcode: int = Field(alias="SubCode")


class MomentCommentItem(Response):
    """时刻动态评论流中的单条评论记录.

    Attributes:
        cmid: 评论 ID.
        seq_no: 评论序号.
        content: 评论正文.
        encrypt_uin: 加密 UIN.
        pub_time: 发布时间戳.
        praise_num: 点赞数.
        reply_cnt: 回复数.
        state: 评论状态.
        is_self: 是否为本人评论.
        location: 位置文案.
        phone_type: 设备类型文案.
        pic: 配图地址.
        pic_size: 配图尺寸信息.
        song_ts_elems: 歌曲时间轴元素.
        hash_tag_list: 话题标签列表.
        little_tails: 尾巴挂件列表.
    """

    cmid: str = Field(alias="CmId")
    seq_no: str = Field(alias="SeqNo")
    content: str = Field(alias="Content")
    encrypt_uin: str = Field(alias="EncryptUin")
    pub_time: int = Field(alias="PubTime")
    praise_num: int = Field(alias="PraiseNum")
    reply_cnt: int = Field(alias="ReplyCnt")
    state: int = Field(alias="State")
    is_self: int = Field(alias="IsSelf")
    location: str = Field(alias="Location")
    phone_type: str = Field(alias="PhoneType")
    pic: str = Field(alias="Pic")
    pic_size: str = Field(alias="PicSize")
    song_ts_elems: list[dict[str, Any]] = Field(default_factory=list, alias="SongTsElems")
    hash_tag_list: list[dict[str, Any]] = Field(default_factory=list, alias="HashTagList")
    little_tails: list[dict[str, Any]] = Field(default_factory=list, alias="LittleTails")


class MomentCommentResponse(Response):
    """时刻评论列表接口的响应体.

    Attributes:
        comments: 当前页时刻评论列表.
        has_more: 是否还有更多结果.
        next_pos: 下一页游标.
        hint: 提示文案.
        prev_list_loaded: 前序列表是否已加载.
        map_cm_ext: 评论扩展信息映射.
    """

    comments: list[MomentCommentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.CmList[*]"})
    has_more: int = Field(alias="HasMore")
    next_pos: str = Field(default="", alias="NextPos")
    hint: str = Field(alias="Hint")
    prev_list_loaded: int = Field(alias="PrevListLoaded")
    map_cm_ext: dict[str, dict[str, Any]] = Field(default_factory=dict, alias="MapCmExt")


class AddCommentResponse(Response):
    """添加评论接口的响应体.

    Attributes:
        subcode: 响应子代码.
        msg: 响应消息.
        id: 新增评论 ID.
        parent: 父评论 ID.
        floor: 楼层号.
        verify_url: 验证码 URL (如果需要).
    """

    subcode: int = Field(alias="SubCode")
    msg: str = Field(alias="Msg")
    id: str = Field(alias="AddedCmId")
    parent: str = Field(alias="ParentCmId")
    floor: int = Field(json_schema_extra={"jsonpath": "$.Floor.Num"})
    verify_url: str = Field(alias="VerifyUrl")
