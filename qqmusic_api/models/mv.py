"""MV API 返回模型定义."""

from typing import Any

from pydantic import Field

from .base import MV, Singer
from .request import Response


class MvDetail(MV):
    """MV 详情接口返回的单个视频条目.

    Attributes:
        cover_pic: MV 封面地址.
        duration: MV 时长.
        singers: MV 歌手列表.
        video_switch: MV 开关位.
        msg: 附加消息.
        desc: MV 描述.
        playcnt: MV 播放量.
        pubdate: 发布时间戳.
        isfav: 是否已收藏.
        gmid: 全局媒体标识.
        uploader_headurl: 上传者头像.
        uploader_nick: 上传者昵称.
        uploader_encuin: 上传者加密 UIN.
        uploader_uin: 上传者 UIN.
        uploader_hasfollow: 是否已关注上传者.
        uploader_follower_num: 上传者粉丝数.
        related_songs: 关联歌曲 ID 列表.
    """

    cover_pic: str
    duration: int
    singers: list[dict[str, Any]]
    video_switch: int
    msg: str
    desc: str
    playcnt: int
    pubdate: int
    isfav: int
    gmid: str
    uploader_headurl: str
    uploader_nick: str
    uploader_encuin: str
    uploader_uin: str
    uploader_hasfollow: int
    uploader_follower_num: int
    related_songs: list[int]


class GetMvDetailResponse(Response):
    """MV 详情接口的响应体.

    Attributes:
        data: 以 VID 为键的 MV 详情映射.
    """

    data: dict[str, MvDetail] = Field(json_schema_extra={"jsonpath": "$"})


class MvUrlItem(Response):
    """单一路径规格下的 MV 播放地址信息.

    Attributes:
        url: 直连地址列表.
        freeflow_url: 免流地址列表.
        comm_url: 通用地址列表.
        cn: 文件名.
        vkey: 播放令牌.
        expire: 过期时间.
        code: 结果码.
        filetype: 文件类型.
        m3u8: m3u8 地址.
        new_file_type: 新文件类型标识.
        format: 编码格式.
        file_size: 文件大小.
    """

    url: list[str]
    freeflow_url: list[str]
    comm_url: list[str]
    cn: str
    vkey: str
    expire: int
    code: int
    filetype: int
    m3u8: str
    new_file_type: int = Field(validation_alias="newFileType")
    format: int
    file_size: int = Field(validation_alias="fileSize")


class MvUrlSet(Response):
    """同一 MV 在不同协议下的播放地址集合.

    Attributes:
        mp4: MP4 地址列表.
        hls: HLS 地址列表.
        svp_flag: 是否支持超清能力标记.
        duration: MV 时长.
    """

    mp4: list[MvUrlItem]
    hls: list[MvUrlItem]
    svp_flag: int
    duration: int


class GetMvUrlsResponse(Response):
    """MV 播放地址接口的响应体.

    Attributes:
        data: 以 MV 标识分组的播放地址集合.
    """

    data: dict[str, MvUrlSet] = Field(json_schema_extra={"jsonpath": "$"})


class MvListItem(MV):
    """MV 分类列表中的单个 MV 摘要.

    Attributes:
        singers: 歌手列表.
        subtitle: MV 副标题.
        playcnt: 播放量.
        pubdate: 发布时间戳.
        duration: 时长 (秒).
        picurl: 封面图片地址.
    """

    singers: list[Singer] = Field(default_factory=list)
    subtitle: str = ""
    playcnt: int = 0
    pubdate: int = 0
    duration: int = 0
    picurl: str = ""


class GetMvListResponse(Response):
    """MV 分类列表接口的响应体.

    Attributes:
        total: 该分类条件下的 MV 总数.
        items: 当前页 MV 列表.
    """

    total: int = 0
    items: list[MvListItem] = Field(default_factory=list, validation_alias="list")
