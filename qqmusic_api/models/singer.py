"""Singer API 返回模型定义."""

from typing import Annotated, Any

from pydantic import AliasChoices, Field

from ._validator import NoneOrZeroToEmptyStr, NoneToEmptyList
from .base import MV, Album, Singer, Song
from .request import Response


class TagOption(Response):
    """歌手筛选标签项.

    Attributes:
        id: 标签 ID.
        name: 标签名称.
    """

    id: int
    name: str = ""


class SingerBrief(Singer):
    """歌手列表条目.

    Attributes:
        id: 歌手 ID.
        mid: 歌手 MID.
        name: 歌手名称.
        pmid: 图片标识.
        area_id: 地区 ID.
        country_id: 国家或地区 ID.
        country: 国家或地区名称.
        other_name: 别名.
        spell: 拼音.
        trend: 趋势标记.
        concern_num: 关注数.
        singer_pic: 歌手图片地址.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("singer_id", "singerId", "id"))
    mid: str = Field(default="", validation_alias=AliasChoices("singer_mid", "singerMid", "mid"))
    name: str = Field(default="", validation_alias=AliasChoices("singer_name", "singerName", "name"))
    pmid: str = Field(default="", validation_alias=AliasChoices("singer_pmid", "singerPmid", "pmid"))
    area_id: int = -1
    country_id: int = -1
    country: str = ""
    other_name: str = ""
    spell: str = ""
    trend: int = 0
    concern_num: int = Field(default=0, alias="concernNum")
    singer_pic: str = ""


class SingerTagData(Response):
    """歌手筛选标签集合.

    Attributes:
        area: 地区标签列表.
        genre: 流派标签列表.
        sex: 性别标签列表.
        index: 索引标签列表.
    """

    area: Annotated[list[TagOption], NoneToEmptyList] = Field(default_factory=list)
    genre: Annotated[list[TagOption], NoneToEmptyList] = Field(default_factory=list)
    sex: Annotated[list[TagOption], NoneToEmptyList] = Field(default_factory=list)
    index: Annotated[list[TagOption], NoneToEmptyList] = Field(default_factory=list)


class SingerTypeListResponse(Response):
    """歌手列表响应.

    Attributes:
        area: 当前地区筛选值.
        sex: 当前性别筛选值.
        genre: 当前流派筛选值.
        singerlist: 当前返回的歌手列表.
        code: 返回码.
        hotlist: 热门歌手列表.
        tags: 可选筛选标签集合.
    """

    area: int = -100
    sex: int = -100
    genre: int = -100
    singerlist: list[SingerBrief] = Field(default_factory=list)
    code: int = 0
    hotlist: list[SingerBrief] = Field(default_factory=list)
    tags: SingerTagData = Field(default_factory=SingerTagData)


class SingerIndexPageResponse(SingerTypeListResponse):
    """按索引分页的歌手列表响应.

    Attributes:
        index: 当前索引筛选值.
        total: 总数量.
    """

    index: int = -100
    total: int = 0


class HomepageBaseInfo(Response):
    """歌手主页基础信息.

    Attributes:
        encrypt_uin: 加密 UIN.
        background_image: 背景图地址.
        avatar: 头像地址.
        name: 展示名称.
        is_host: 是否为主页所有者.
        is_singer: 是否为歌手账号.
        user_type: 用户类型标记.
    """

    encrypt_uin: str = Field(default="", alias="EncryptedUin")
    background_image: str = Field(default="", alias="BackgroundImage")
    avatar: str = Field(default="", alias="Avatar")
    name: str = Field(default="", alias="Name")
    is_host: int = Field(default=0, alias="IsHost")
    is_singer: int = Field(default=0, alias="IsSinger")
    user_type: int = Field(default=0, alias="UserType")


class HomepageSinger(Response):
    """歌手主页歌手信息.

    Attributes:
        id: 歌手 ID.
        mid: 歌手 MID.
        name: 歌手名称.
        type: 歌手类型.
        singer_pic: 歌手图片地址.
        singer_pmid: 歌手图片标识.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("SingerID", "singerID", "singer_id"))
    mid: str = Field(default="", validation_alias=AliasChoices("SingerMid", "singerMid", "singer_mid"))
    name: str = Field(default="", validation_alias=AliasChoices("Name", "name", "singerName"))
    type: int = Field(default=-1, validation_alias=AliasChoices("SingerType", "type"))
    singer_pic: str = Field(default="", alias="SingerPic")
    singer_pmid: str = Field(default="", alias="SingerPMid")


class TabMeta(Response):
    """主页标签元信息.

    Attributes:
        tab_id: 标签页 ID.
        tab_name: 标签页名称.
        title: 标签页标题.
    """

    tab_id: str = Field(default="", alias="TabID")
    tab_name: str = Field(default="", alias="TabName")
    title: str = Field(default="", alias="Title")


class AlbumBrief(Album):
    """歌手相关专辑条目.

    Attributes:
        id: 专辑 ID.
        mid: 专辑 MID.
        name: 专辑名称.
        subtitle: 专辑副标题.
        time_public: 发行日期.
        total_num: 曲目数.
        album_type: 专辑类型文案.
        singer_name: 歌手名称.
        tags: 标签列表.
    """

    id: int = Field(default=-1, alias="albumID")
    mid: str = Field(default="", alias="albumMid")
    name: str = Field(default="", alias="albumName")
    subtitle: str = Field(default="", alias="albumTranName")
    time_public: str = Field(default="", alias="publishDate")
    total_num: int = Field(default=0, alias="totalNum")
    album_type: str = Field(default="", alias="albumType")
    singer_name: str = Field(default="", alias="singerName")
    tags: Annotated[list[str], NoneToEmptyList] = Field(default_factory=list)


class VideoBrief(MV):
    """歌手视频条目.

    Attributes:
        id: MV ID.
        vid: MV VID.
        type: MV 类型.
        title: 标题.
        picurl: 封面地址.
        picformat: 封面格式标记.
        duration: 时长.
        playcnt: 播放量.
        pubdate: 发布时间戳.
        icon_type: 图标类型.
    """

    id: int = Field(default=-1, alias="mvid")
    vid: str = ""
    type: int = -1
    title: str = ""
    picurl: str = ""
    picformat: int = 0
    duration: int = 0
    playcnt: int = 0
    pubdate: int = 0
    icon_type: int = 0


class HomepageTabDetailResponse(Response):
    """歌手主页标签详情响应.

    Attributes:
        tab_id: 当前标签页 ID.
        has_more: 是否还有更多结果.
        need_show_tab: 是否需要展示标签.
        order: 排序值.
        tab_list: 标签页元信息列表.
        introduction_tab: 简介标签内容.
        song_tab: 歌曲标签内容.
        album_tab: 专辑标签内容.
        video_tab: 视频标签内容.
    """

    tab_id: str = Field(default="", alias="TabID")
    has_more: int = Field(default=0, alias="HasMore")
    need_show_tab: int = Field(default=0, alias="NeedShowTab")
    order: int = Field(default=0, alias="Order")
    tab_list: Annotated[list[TabMeta], NoneToEmptyList] = Field(default_factory=list, alias="TabList")
    introduction_tab: Annotated[list[dict[str, Any]], NoneToEmptyList] = Field(
        default_factory=list,
        json_schema_extra={"jsonpath": "$.IntroductionTab.List"},
    )
    song_tab: Annotated[list[Song], NoneToEmptyList] = Field(
        default_factory=list, json_schema_extra={"jsonpath": "$.SongTab.List[*]"}
    )
    album_tab: Annotated[list[AlbumBrief], NoneToEmptyList] = Field(
        default_factory=list, json_schema_extra={"jsonpath": "$.AlbumTab.AlbumList[*]"}
    )
    video_tab: Annotated[list[VideoBrief], NoneToEmptyList] = Field(
        default_factory=list, json_schema_extra={"jsonpath": "$.VideoTab.VideoList[*]"}
    )


class HomepageHeaderResponse(Response):
    """歌手主页头部响应.

    Attributes:
        status: 状态码.
        singer: 歌手信息.
        base_info: 主页基础信息.
        tab_detail: 默认标签页详情.
        prompt: 附加提示信息.
    """

    status: int = Field(alias="Status")
    singer: HomepageSinger = Field(json_schema_extra={"jsonpath": "$.Info.Singer"})
    base_info: HomepageBaseInfo = Field(json_schema_extra={"jsonpath": "$.Info.BaseInfo"})
    tab_detail: HomepageTabDetailResponse = Field(alias="TabDetail")
    prompt: dict[str, Any] = Field(default_factory=dict, alias="Prompt")


class SingerBasicInfo(Singer):
    """歌手详情基础信息.

    Attributes:
        id: 歌手 ID.
        mid: 歌手 MID.
        name: 歌手名称.
        type: 歌手类型.
        pmid: 图片标识.
        has_photo: 是否有照片.
        wikiurl: 百科链接.
    """

    id: int = Field(default=-1, alias="singer_id")
    mid: str = Field(default="", alias="singer_mid")
    name: str = Field(default="", alias="name")
    type: int = Field(default=-1, alias="type")
    pmid: str = Field(default="", alias="singer_pmid")
    has_photo: int = Field(default=0, alias="has_photo")
    wikiurl: str = ""


class SingerExtraInfo(Response):
    """歌手详情扩展信息.

    Attributes:
        area: 地区信息.
        desc: 描述文本.
        tag: 标签文本.
        identity: 身份信息.
        instrument: 擅长乐器.
        genre: 流派信息.
        foreign_name: 外文名.
        birthday: 生日.
        enter: 入驻或出道信息.
        blog_flag: 博客标记.
    """

    area: Annotated[str, NoneOrZeroToEmptyStr] = ""
    desc: str = ""
    tag: str = ""
    identity: Annotated[str, NoneOrZeroToEmptyStr] = ""
    instrument: Annotated[str, NoneOrZeroToEmptyStr] = ""
    genre: Annotated[str, NoneOrZeroToEmptyStr] = ""
    foreign_name: str = ""
    birthday: str = ""
    enter: Annotated[str, NoneOrZeroToEmptyStr] = ""
    blog_flag: int = Field(default=0, alias="blogFlag")


class SingerDetail(Response):
    """歌手详情条目.

    Attributes:
        basic_info: 基础信息.
        ex_info: 扩展信息.
        wiki: 百科或扩展说明数据.
        group_list: 组合成员列表.
        photos: 照片列表.
        group_info: 组合附加信息.
    """

    basic_info: SingerBasicInfo = Field(alias="basic_info")
    ex_info: SingerExtraInfo = Field(default_factory=SingerExtraInfo, alias="ex_info")
    wiki: str = ""
    group_list: Annotated[list[dict[str, Any]], NoneToEmptyList] = Field(default_factory=list)
    photos: Annotated[list[dict[str, Any]], NoneToEmptyList] = Field(default_factory=list)
    group_info: Annotated[list[dict[str, Any]], NoneToEmptyList] = Field(default_factory=list)


class SingerDetailResponse(Response):
    """歌手详情响应.

    Attributes:
        singer_list: 歌手详情列表.
    """

    singer_list: list[SingerDetail] = Field(default_factory=list, alias="singer_list")


class SimilarSinger(Singer):
    """相似歌手条目.

    Attributes:
        id: 歌手 ID.
        mid: 歌手 MID.
        name: 歌手名称.
        pmid: 图片标识.
        singer_pic: 歌手图片地址.
        trace: 追踪信息.
        abt: 补充文案.
        tf: 附加标记.
    """

    id: int = Field(default=-1, alias="singerId")
    mid: str = Field(default="", alias="singerMid")
    name: str = Field(default="", alias="singerName")
    pmid: str = Field(default="", alias="pic_mid")
    singer_pic: str = Field(default="", alias="singerPic")
    trace: str = ""
    abt: str = ""
    tf: str = ""


class SimilarSingerResponse(Response):
    """相似歌手列表响应.

    Attributes:
        singerlist: 相似歌手列表.
        code: 返回码.
        err_msg: 错误消息.
    """

    singerlist: Annotated[list[SimilarSinger], NoneToEmptyList] = Field(default_factory=list)
    code: int = 0
    err_msg: str = Field(default="", alias="errMsg")


class SingerSongListResponse(Response):
    """歌手歌曲列表响应.

    Attributes:
        singer_mid: 歌手 MID.
        total_num: 歌曲总数.
        song_list: 当前页歌曲列表.
    """

    singer_mid: str = Field(default="", alias="singerMid")
    total_num: int = Field(default=0, alias="totalNum")
    song_list: Annotated[list[Song], NoneToEmptyList] = Field(
        default_factory=list, json_schema_extra={"jsonpath": "$.songList[*].songInfo"}
    )


class SingerAlbumListResponse(Response):
    """歌手专辑列表响应.

    Attributes:
        singer_mid: 歌手 MID.
        total: 专辑总数.
        album_list: 当前页专辑列表.
    """

    singer_mid: str = Field(default="", alias="singerMid")
    total: int = 0
    album_list: Annotated[list[AlbumBrief], NoneToEmptyList] = Field(default_factory=list, alias="albumList")


class SingerMvListResponse(Response):
    """歌手 MV 列表响应.

    Attributes:
        total: MV 总数.
        mv_list: 当前页 MV 列表.
    """

    total: int = 0
    mv_list: Annotated[list[VideoBrief], NoneToEmptyList] = Field(default_factory=list, alias="list")
