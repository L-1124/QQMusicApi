"""Song API 返回模型定义."""

from pydantic import Field

from .base import MV, Singer, Song, SongList
from .request import Response


class QuerySongResponse(Response):
    """批量歌曲查询响应.

    Attributes:
        tracks: 按请求条件返回的歌曲对象列表.
    """

    tracks: list[Song] = Field(default_factory=list)


class UrlinfoItem(Response):
    """单个文件授权结果.

    Attributes:
        mid: 歌曲 mid.
        filename: 请求的目标文件名.
        purl: 相对下载路径,需要与 CDN 域名拼接后才能访问.
        vkey: 资源访问令牌,歌曲文件通常依赖该字段完成鉴权.
        ekey: 加密资源解密密钥.
        result: 单个文件的业务结果码.常见值为 `0`(成功)、`104003`(无权限)、
                `104004`(VKey 获取失败)、`104013`(播放设备受限).
    """

    mid: str = Field(alias="songmid")
    filename: str
    purl: str
    vkey: str
    ekey: str
    result: int


class GetSongUrlsResponse(Response):
    """歌曲播放地址响应.

    Attributes:
        expiration: 链接过期时间 (秒).
        data: 每个目标文件对应的授权与路径信息.
    """

    expiration: int = 0
    data: list[UrlinfoItem] = Field(default_factory=list, alias="midurlinfo")


class ContentItem(Response):
    """表示 GetSongDetail 返回的内容项.

    Attributes:
        id: 内容项 ID.
        value: 内容项值.
        show_type: 内容项展示类型.
        jumpurl: 内容项跳转链接.
    """

    id: int
    value: str
    show_type: int
    jumpurl: str


class GetSongDetailResponse(Response):
    """歌曲详情响应.

    除歌曲基础信息外,还按内容分组返回发行公司、流派、语言、发布时间等补充资料.

    Attributes:
        company: 发行公司信息.
        genre: 歌曲类型信息.
        intro: 歌曲简介信息.
        lan: 语言信息.
        pub_time: 发布时间信息.
        extras: 额外信息.
        track: 歌曲基本信息.
    """

    company: list[ContentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.info.company.content"})
    genre: list[ContentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.info.genre.content"})
    intro: list[ContentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.info.intro.content"})
    lan: list[ContentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.info.lan.content"})
    pub_time: list[ContentItem] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.info.pub_time.content"})
    extras: dict[str, str] = Field(default_factory=dict)
    track: Song = Field(alias="track_info")


class SimilarSongGroup(Response):
    """一组相似歌曲推荐卡片.

    一个分组对应一个推荐标题及其下挂载的歌曲列表.

    Attributes:
        title_template: 推荐分组的标题模板.
        title_content: 标题模板中的实际内容.
        song: 当前推荐分组下的歌曲列表.
    """

    title_template: str
    title_content: str
    song: list[Song] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.songs[*].track"})


class GetSimilarSongResponse(Response):
    """相似歌曲推荐响应.

    Attributes:
        tag: 本次推荐附带的歌曲标签列表.
        song: 按卡片分组组织的相似歌曲结果.
    """

    tag: list[dict] = Field(default_factory=list, alias="songTagInfoList")
    song: list[SimilarSongGroup] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.vecSongNew"})


class SongLabel(Response):
    """歌曲标签项.

    Attributes:
        id: 标签 ID.
        tag_txt: 标签文本.
        tag_icon: 标签图标地址.
        tag_url: 标签跳转链接.
        tag_type: 标签类型.
        species: 标签所属分类.
    """

    id: int
    tag_txt: str = Field(alias="tagTxt")
    tag_icon: str = Field(alias="tagIcon")
    tag_url: str = Field(alias="tagUrl")
    tag_type: int = Field(alias="tagType")
    species: int


class GetSongLabelsResponse(Response):
    """获取歌曲标签结果.

    Attributes:
        labels: 歌曲标签列表.
    """

    labels: list[SongLabel] = Field(default_factory=list)


class RelatedPlaylist(SongList):
    """歌曲详情页关联歌单中的单个歌单摘要.

    Attributes:
        creator: 歌单创建者名称.
    """

    creator: str = ""


class GetRelatedSonglistResponse(Response):
    """歌曲关联歌单响应.

    Attributes:
        has_more: 是否还有更多结果.
        songlist: 按推荐分组展开后的相关歌单列表.
    """

    has_more: int = Field(alias="hasMore")
    songlist: list[RelatedPlaylist] = Field(
        default_factory=list,
        json_schema_extra={"jsonpath": "$.vecPlaylistNew[*].playlists[*]"},
    )


class RelatedMv(MV):
    """歌曲详情页关联 MV 的摘要信息.

    Attributes:
        picurl: MV 封面.
        playcnt: MV 播放量.
        singers: MV 关联歌手列表.
    """

    class MVSinger(Singer):
        """关联 MV 中的歌手摘要信息.

        Attributes:
            picurl: 歌手头像地址.
        """

        picurl: str

    picurl: str
    playcnt: int
    singers: list[MVSinger] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.singers"})


class GetRelatedMvResponse(Response):
    """歌曲关联 MV 响应.

    Attributes:
        has_more: 是否还有更多结果.
        mv: 当前返回的相关 MV 列表.
    """

    has_more: int = Field(alias="hasmore")
    mv: list[RelatedMv] = Field(default_factory=list, alias="list")


class GetOtherVersionResponse(Response):
    """获取歌曲其他版本结果.

    Attributes:
        data: 其他版本歌曲列表.
    """

    data: list[Song] = Field(default_factory=list, alias="versionList")


class SongProducer(Response):
    """歌曲制作人项.

    Attributes:
        type: 制作人类型.
        name: 制作人名称.
        icon: 制作人头像.
        scheme: 制作人跳转链接.
        singer_mid: 制作人 singer mid.
        follow: 关注状态.
    """

    type: int = Field(alias="Type")
    name: str = Field(alias="Name")
    icon: str = Field(alias="Icon")
    scheme: str = Field(alias="Scheme")
    singer_mid: str = Field(alias="SingerMid")
    follow: int = Field(alias="Follow")


class SongProducerGroup(Response):
    """歌曲制作人信息分组.

    Attributes:
        title: 分组标题.
        producers: 该分组下的制作人列表.
        type: 分组类型.
    """

    title: str = Field(alias="Title")
    producers: list[SongProducer] = Field(alias="Producers")
    type: int = Field(alias="Type")


class GetProducerResponse(Response):
    """歌曲制作人响应.

    Attributes:
        data: 按职责分组的制作人列表.
        reinforce_msg: 附带的摘要说明文案.
    """

    data: list[SongProducerGroup] = Field(default_factory=list, alias="Lst")
    reinforce_msg: str = Field(default="", alias="ReinforceMsg")


class SheetMusic(Response):
    """曲谱项.

    Attributes:
        score_mid: 曲谱 MID.
        score_name: 曲谱名称.
        pic_urls: 曲谱图片列表.
        version: 曲谱版本说明.
        tonality: 调号.
        score_type: 曲谱类型.
        score_type_text: 曲谱类型文本.
        uploader: 上传者.
        view_frequency: 浏览量.
        tonality2: 第二调号值.
        author: 作者.
        composer: 作曲.
        lyricist: 作词.
        singer: 演唱者.
        performer: 演奏者.
        song_mid: 关联歌曲 MID.
        sub_name: 曲谱副标题.
        url: 曲谱详情链接.
        album_url: 专辑链接.
        ins_type: 乐器类型.
        ins_type_text: 乐器类型文本.
        cover_url: 乐器封面.
        difficulty: 难度.
        sheet_file: 曲谱文件地址.
    """

    score_mid: str = Field(alias="scoreMID")
    score_name: str = Field(alias="scoreName")
    pic_urls: list[str] = Field(alias="picURLs")
    version: str
    tonality: int
    score_type: int = Field(alias="scoreType")
    score_type_text: str = Field(alias="strScoreType")
    uploader: str
    view_frequency: int = Field(alias="viewFrequency")
    tonality2: int
    author: str
    composer: str
    lyricist: str
    singer: str
    performer: str
    song_mid: str = Field(alias="songMID")
    sub_name: str = Field(alias="subName")
    url: str
    album_url: str = Field(alias="albumURL")
    ins_type: int = Field(alias="insType")
    ins_type_text: str = Field(alias="strInsType")
    cover_url: str = Field(alias="coverURL")
    difficulty: str
    sheet_file: str = Field(alias="sheetFile")


class GetSheetResponse(Response):
    """歌曲相关曲谱响应.

    Attributes:
        result: 当前返回的曲谱列表.
        total_map: 各曲谱类型对应的数量聚合.
    """

    result: list[SheetMusic]
    total_map: dict[str, int] = Field(alias="totalMap")


class GetFavNumResponse(Response):
    """歌曲收藏人数响应.

    Attributes:
        numbers: 以歌曲标识为键的收藏人数原始值映射.
        show: 对应的收藏人数展示文案映射.
    """

    numbers: dict[str, int] = Field(alias="m_numbers")
    show: dict[str, str] = Field(alias="m_show")


class CdnDispatchSipInfo(Response):
    """CDN 调度中的单个节点信息.

    Attributes:
        cdn: CDN 节点地址.
        quic: 是否支持 QUIC.
        ipstack: IP 栈类型.
        quichost: QUIC 主机名.
        plaintext_quic: 是否支持明文 QUIC.
        encrypt_quic: 是否支持加密 QUIC.
    """

    cdn: str = ""
    quic: int = 0
    ipstack: int = 0
    quichost: str = ""
    plaintext_quic: int = Field(default=0, alias="plaintextquic")
    encrypt_quic: int = Field(default=0, alias="encryptquic")


class GetCdnDispatchResponse(Response):
    """获取音频 CDN 调度响应.

    仅保留歌曲 URL 构建与缓存控制所需字段.

    Attributes:
        retcode: 接口返回码.
        sip: 可用 CDN 根地址列表.
        sipinfo: 可用 CDN 节点明细列表.
        test_file: 用于测试 CDN 可用性的文件路径.
        expiration: 数据有效期 (秒).
        refresh_time: 建议刷新间隔 (秒).
        cache_time: 建议缓存时长 (秒).
    """

    retcode: int
    sip: list[str] = Field(default_factory=list)
    sipinfo: list[CdnDispatchSipInfo] = Field(default_factory=list)
    test_file: str = Field(alias="keepalivefile")
    expiration: int
    refresh_time: int = Field(alias="refreshTime")
    cache_time: int = Field(alias="cacheTime")
