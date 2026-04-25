"""定义多个接口共享的基础业务实体模型."""

from typing import Final, Literal

from pydantic import AliasChoices, Field

from .request import Response

CoverSize = Literal[150, 300, 500, 800, 1200, 1500]

_PHOTO_NEW_SIZE_SEGMENTS: Final[dict[int, str]] = {
    150: "R150x150",
    300: "R300x300",
    500: "R500x500",
    800: "R800x800",
    1200: "R1200x1200",
    1500: "R1500x1500",
}


def _normalize_cover_size(size: CoverSize) -> str:
    """返回 `photo_new` 模板使用的尺寸片段."""
    try:
        return _PHOTO_NEW_SIZE_SEGMENTS[size]
    except KeyError as exc:
        raise ValueError("not supported size") from exc


def _build_photo_new_cover_url(kind: str, mid: str, size: CoverSize) -> str:
    """按 `photo_new` 规则拼接封面链接."""
    normalized_mid = mid.strip()
    if not normalized_mid:
        return ""

    return f"https://y.gtimg.cn/music/photo_new/{kind}{_normalize_cover_size(size)}M000{normalized_mid}.jpg"


class Singer(Response):
    """表示接口响应中常见的歌手摘要信息.

    Attributes:
        id: 歌手数字 ID.
        mid: 歌手 Media MID, 用于请求歌手详情的核心参数.
        name: 歌手名称.
        title: 歌手展示标题, 通常与名称一致.
        type: 歌手类型, 如 0 表示艺人, 1 表示组合.
        uin: 与歌手关联的用户 ID.
        pmid: 图片 Media ID, 用于拼接歌手头像 URL.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("id", "singerID", "singerId", "SingerID", "singer_id"))
    mid: str = Field(
        default="",
        validation_alias=AliasChoices("mid", "singerMid", "singerMID", "SingerMid", "singer_mid"),
    )
    name: str = Field(default="", validation_alias=AliasChoices("name", "singerName", "singer_name"))
    title: str = Field(default="", validation_alias=AliasChoices("title", "singerName", "name"))
    type: int = Field(default=-1, validation_alias=AliasChoices("type", "SingerType", "vt"))
    uin: int = -1
    pmid: str = Field(default="", validation_alias=AliasChoices("pmid", "singerPmid", "singer_pmid", "pic_mid"))

    def cover_url(self, size: CoverSize = 300) -> str:
        """获取歌手封面链接."""
        return _build_photo_new_cover_url("T001", self.mid or self.pmid, size)


class Album(Response):
    """表示接口响应中的专辑摘要信息.

    Attributes:
        id: 专辑数字 ID.
        mid: 专辑 Media MID, 用于请求专辑详情的核心参数.
        name: 专辑名称.
        title: 专辑展示标题.
        subtitle: 专辑副标题.
        time_public: 发行日期, 格式通常为 YYYY-MM-DD.
        pmid: 图片 Media ID, 用于拼接封面 URL.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("id", "albumID"))
    mid: str = Field(default="", validation_alias=AliasChoices("mid", "albumMid", "albumMID", "albummid"))
    name: str = Field(default="", validation_alias=AliasChoices("name", "albumName"))
    title: str = Field(default="", validation_alias=AliasChoices("title", "albumName", "name"))
    subtitle: str = Field(default="", validation_alias=AliasChoices("subtitle", "albumTranName"))
    time_public: str = Field(default="", validation_alias=AliasChoices("time_public", "publish_date", "publishDate"))
    pmid: str = Field(default="", validation_alias=AliasChoices("pmid", "logo"))

    def cover_url(self, size: CoverSize = 300) -> str:
        """获取专辑封面链接."""
        return _build_photo_new_cover_url("T002", self.mid or self.pmid, size)


class File(Response):
    """歌曲文件信息.

    包含歌曲在不同音质等级下的文件大小(字节)信息.

    Attributes:
        media_mid: 基础媒体标识符, 用于拼接文件名.
        size_24aac: 极低品质 AAC 大小.
        size_48aac: 低品质 AAC 大小.
        size_96aac: 流畅音质 AAC 大小.
        size_192ogg: HQ 高品质 OGG 大小 (192k).
        size_192aac: HQ 高品质 AAC 大小 (192k).
        size_128mp3: 标准音质 MP3 大小 (128k).
        size_320mp3: HQ 高品质 MP3 大小 (320k).
        size_flac: SQ 无损音质 FLAC 大小.
        size_dts: DTS:X 音效文件大小.
        size_try: 试听片段文件大小.
        try_begin: 试听片段开始时间 (毫秒).
        try_end: 试听片段结束时间 (毫秒).
        size_96ogg: 流畅音质 OGG 大小 (96k).
        size_dolby: 杜比全景声文件大小.
        size_new: 现代高级音质数组, 包含臻品系列大小.
            - [0]: 臻品母带 (24Bit/192kHz).
            - [1]: 臻品音质 2.0 (银河音效).
            - [2]: 臻品全景声 5.1 (空间音频).
            - [3]: HQ 高品质 (OGG 320k).
            - [4]: 黑胶唱片 (模拟质感).
            - [5]: SQ 无损音质 (OGG 640k).
            - [6]: 臻品全景声 7.1.4.
            - [7]: TQ 标准音质 (NAC 极致压缩).
            - [9]: DTS:X (5.1 环绕声).
    """

    media_mid: str = ""
    size_24aac: int = -1
    size_48aac: int = -1
    size_96aac: int = -1
    size_192ogg: int = -1
    size_192aac: int = -1
    size_128mp3: int = -1
    size_320mp3: int = -1
    size_flac: int = -1
    size_dts: int = -1
    size_try: int = -1
    try_begin: int = -1
    try_end: int = -1
    size_96ogg: int = -1
    size_dolby: int = -1
    size_new: list[int] = Field(default_factory=list)


class Pay(Response):
    """表示歌曲在播放、下载与付费上的权限信息.

    Attributes:
        pay_month: 绿钻或付费包权限标识, 1 表示需要.
        price_track: 单曲售价, 单位为分.
        price_album: 专辑售价, 单位为分.
        pay_play: 播放付费标识.
        pay_down: 下载付费标识.
        pay_status: 支付状态.
        time_free: 免费试听或限免时长信息.
    """

    pay_month: int = -1
    price_track: int = -1
    price_album: int = -1
    pay_play: int = -1
    pay_down: int = -1
    pay_status: int = -1
    time_free: int = -1


class MV(Response):
    """表示歌曲关联的 MV 摘要信息.

    Attributes:
        id: MV 数字 ID.
        vid: MV VID, 常用于请求 MV 详情或播放地址.
        type: MV 类型.
        name: MV 名称.
        title: MV 展示标题.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("id", "sid", "mvid", "singerId"))
    vid: str = ""
    type: int = Field(default=-1, validation_alias=AliasChoices("vt", "type"))
    name: str = Field(default="", validation_alias=AliasChoices("name", "mvname", "title"))
    title: str = Field(default="", validation_alias=AliasChoices("title", "title_main", "name"))


class SongList(Response):
    """表示歌单或曲库目录的摘要信息.

    Attributes:
        id: 歌单数字 ID.
        dirid: 目录 ID.
        title: 歌单标题.
        picurl: 歌单封面地址.
        desc: 歌单简介.
        songnum: 歌曲数量.
        listennum: 播放量.
    """

    id: int = Field(default=-1, validation_alias=AliasChoices("id", "tid", "dissid"))
    dirid: int = Field(default=0, validation_alias=AliasChoices("dirid", "dirId"))
    title: str = Field(default="", validation_alias=AliasChoices("title", "dissname", "name", "dirName"))
    picurl: str = Field(default="", validation_alias=AliasChoices("picurl", "cover", "logo", "picUrl"))
    desc: str = Field(default="", validation_alias=AliasChoices("desc", "description"))
    songnum: int = Field(default=0, validation_alias=AliasChoices("songnum", "songNum", "song_cnt"))
    listennum: int | str = Field(default=0, validation_alias=AliasChoices("listennum", "playCnt", "play_cnt"))


class Song(Response):
    """歌曲基础模型.

    包含歌曲的基础识别信息、关联对象、技术参数及播放权限控制.

    Attributes:
        id: 歌曲数字 ID.
        type: 歌曲类型 (1: 普通歌曲; 2: 长音频; 6: 视频/直播等).
        mid: 歌曲 Media MID, 请求播放链接、歌词、详情的核心参数.
        name: 歌曲名称.
        title: 歌曲标题.
        subtitle: 副标题, 如"电影《xxx》插曲".
        singer: 歌手列表.
        album: 专辑信息.
        mv: MV 信息.
        file: 歌曲文件信息.
        pay: 支付属性.
        interval: 时长 (秒).
        isonly: 是否独家 (1: 是).
        language: 语言 ID.
        genre: 音乐流派 ID (见文档 5.3.1 映射表).
        index_cd: CD 索引.
        index_album: 专辑索引.
        time_public: 发行日期, 格式通常为 YYYY-MM-DD.
        status: 歌曲上下架状态 (0: 正常; 1: 下架; 2: 待审核; 3: 仅限部分区域播放).
        label: 唱片公司或特性标签 (如"经典").
        bpm: 每分钟节拍数 (BPM), 对应 JSON 中的 bpm 字段.
        ov: 原版标识 (1: 正宗原版; 0: 翻唱/Live).
        sa: 64 位权益位掩码, 标识高级权益 (HQ/SQ/Hi-Res/Atmos/Master) 及试听状态.
        es: 扩展状态/来源, 用于存放版权或协议层面的附加参数.
        vs: 关联版本与高级媒体 MID 列表.
            - [0]: 标准试听片段 MID (RS02).
            - [3]: 臻品母带完整版 MID (AI00).
            - [4]: 臻品音质 2.0 完整版 MID (Q000).
            - [7]: 杜比全景声试听 MID (DA04).
            - [8]: 臻品音质(银河)试听 MID (QA00).
            - [9]: 纯人声/伴奏轨道 (O801).
            - [11]: 黑胶唱片试听 MID (VA00).
            - [13-17]: AI 臻品音效 (钢琴、古筝、葫芦丝、曲笛、八音盒).
            - [18]: 多轨版媒体 MID (O601).
            - [19-22]: AI 臻品音效 (唢呐、手碟、电吉他、架子鼓).
            - [23]: 人声伴奏试听 MID (O802).
            - [24]: 臻品全景声 7.1.4 完整版 MID (Q003).
            - [26]: AI 臻品音效 - 卡祖笛版.
            - [27]: AI 臻品音效 - 疗愈版.
            - [28]: TQ 标准音质 (NAC) 完整版 MID (TL01).
            - [30]: DTS:X 音效完整版 MID (DT03).
            - [31]: 护耳模式完整版 MID (HE00).
        vi: 变体信息数组.
            - [4]: 试听开始时间 (毫秒).
            - [5]: 试听结束时间 (毫秒).
            - [6]: 音质/格式标记 (1: 支持 NAC).
        vf: 音量平衡数组 (ReplayGain).
            - [0]: 建议增益 (dB).
            - [1]: 信号峰值幅度.
            - [2]: 响度范围.
    """

    id: int
    mid: str
    name: str
    type: int
    title: str = ""
    subtitle: str = ""
    singer: list[Singer]
    album: Album
    mv: MV
    file: File
    pay: Pay
    interval: int
    isonly: int
    language: int
    genre: int
    index_cd: int
    index_album: int
    time_public: str = ""
    status: int
    label: str
    bpm: int
    ov: int
    sa: int
    es: str
    vs: list[str]
    vi: list[int]
    vf: list[float]

    def cover_url(self, size: CoverSize = 300) -> str:
        """获取歌曲封面链接.

        依次使用专辑封面->首个可用歌手封面.

        Args:
            size: 封面大小.
        """
        if self.album.mid or self.album.pmid:
            return self.album.cover_url(size)

        for singer in self.singer:
            if singer.mid or singer.pmid:
                return singer.cover_url(size)

        return ""
