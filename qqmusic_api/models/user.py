"""User API 返回模型定义."""

from typing import Any

from pydantic import AliasChoices, Field

from .base import MV, Album, Singer, SongList
from .request import BaseModel, Response


class UserPlaylistSummary(SongList):
    """用户歌单列表中的单个歌单摘要.

    Attributes:
        id: 歌单 ID.
        dirid: 目录 ID.
        title: 歌单标题.
        picurl: 歌单封面地址.
        songnum: 歌曲数量.
        create_time: 创建时间戳.
        update_time: 更新时间戳.
        uin: 创建者 UIN.
        nick: 创建者昵称.
        desc: 歌单简介.
        bigpic_url: 大图封面地址.
        album_pic_url: 专辑拼接封面地址.
        avatar: 创建者头像.
        ident_icon: 身份图标地址.
        layer_url: 分层装饰地址.
        invalid: 是否失效.
        dir_show: 目录展示标记.
        create_fav_cnt: 创建者收藏量.
        play_cnt: 播放量.
        comment_cnt: 评论数.
        op_type: 操作类型标记.
        sort_weight: 排序权重.
    """

    create_time: int = Field(validation_alias="createTime")
    update_time: int = Field(validation_alias="updateTime")
    uin: str
    nick: str
    bigpic_url: str = Field(validation_alias="bigpicUrl")
    album_pic_url: str = Field(validation_alias="albumPicUrl")
    avatar: str
    ident_icon: str = Field(validation_alias="identIcon")
    layer_url: str = Field(validation_alias="layerUrl")
    invalid: bool
    dir_show: int = Field(validation_alias="dirShow")
    create_fav_cnt: int = Field(validation_alias="fav_cnt")
    play_cnt: int
    comment_cnt: int
    op_type: int = Field(validation_alias="opType")
    sort_weight: int = Field(validation_alias="sortWeight")


class UserCreatedSonglistResponse(Response):
    """用户创建歌单列表页响应.

    Attributes:
        total: 歌单总数.
        playlists: 当前页歌单摘要列表.
        deleted_ids: 上游返回的删除歌单 ID 标记.
        finished: 是否已经拉取完成.
    """

    total: int
    playlists: list[UserPlaylistSummary] = Field(json_schema_extra={"jsonpath": "$.v_playlist[*]"})
    deleted_ids: list[int] = Field(validation_alias="v_delTid")
    finished: bool = Field(validation_alias="bFinish")


class UserFavSonglistItem(SongList):
    """用户收藏歌单列表中的单个条目.

    Attributes:
        id: 歌单 ID.
        dirid: 目录 ID.
        title: 歌单标题.
        picurl: 歌单封面地址.
        songnum: 歌曲数量.
        uin: 歌单所属用户 UIN.
        nickname: 歌单拥有者昵称.
        create_time: 创建时间戳.
        update_time: 更新时间戳.
        order_time: 收藏排序时间戳.
        dir_show: 目录展示标记.
        dir_type: 目录类型.
        edge_mark: 边角标识.
        layer_url: 分层装饰地址.
        album_pic_url: 专辑拼接封面地址.
        op_type: 操作类型标记.
        sort_weight: 排序权重.
        readtime: 最近读取时间戳.
    """

    uin: str
    nickname: str
    create_time: int = Field(validation_alias="createtime")
    update_time: int = Field(validation_alias="updateTime")
    order_time: int = Field(validation_alias="orderTime")
    dir_show: int = Field(validation_alias="dirShow")
    dir_type: int = Field(validation_alias="dirType")
    edge_mark: str = Field(validation_alias="edgeMark")
    layer_url: str = Field(validation_alias="layerUrl")
    album_pic_url: str = Field(validation_alias="albumPicUrl")
    op_type: int = Field(validation_alias="opType")
    sort_weight: int = Field(validation_alias="sortWeight")
    readtime: int


class UserFavSonglistResponse(Response):
    """用户收藏歌单列表页响应.

    Attributes:
        number: 当前页数量或请求数量.
        total: 收藏歌单总数.
        hasmore: 是否还有更多结果.
        hide: 列表是否隐藏.
        playlists: 当前页收藏歌单列表.
        deleted_ids: 上游返回的删除歌单 ID 列表.
        failed_ids: 拉取失败的歌单 ID 列表.
    """

    number: int
    total: int
    hasmore: int
    hide: bool
    playlists: list[UserFavSonglistItem] = Field(json_schema_extra={"jsonpath": "$.v_list"})
    deleted_ids: list[int] = Field(validation_alias="v_delTids")
    failed_ids: list[int] = Field(validation_alias="v_failTids")


class UserFavAlbumItem(Album):
    """用户收藏专辑列表中的单个专辑条目.

    Attributes:
        id: 专辑 ID.
        mid: 专辑 MID.
        name: 专辑名称.
        pmid: 专辑封面标识.
        songnum: 专辑曲目数.
        pubtime: 发布时间戳.
        ordertime: 收藏排序时间戳.
        status: 状态标记.
        loc: 位置或来源标记.
        singers: 专辑歌手列表.
    """

    songnum: int
    pubtime: int
    ordertime: int
    status: int
    loc: int
    singers: list[Singer] = Field(validation_alias="v_singer")


class UserFavAlbumResponse(Response):
    """用户收藏专辑列表页响应.

    Attributes:
        number: 当前页数量或请求数量.
        total: 收藏专辑总数.
        hasmore: 是否还有更多结果.
        hide: 列表是否隐藏.
        albums: 当前页收藏专辑列表.
        failed_album_ids: 拉取失败的专辑 ID 列表.
    """

    number: int
    total: int
    hasmore: int
    hide: bool
    albums: list[UserFavAlbumItem] = Field(json_schema_extra={"jsonpath": "$.v_list[*]"})
    failed_album_ids: list[int] = Field(validation_alias="v_failAlbumId")


class UserInfoCard(Response):
    """用户音乐基因页头部卡片信息.

    Attributes:
        head_url: 头像地址.
        nick_name: 昵称.
        signature: 个性签名.
        encryption_account: 加密账号标识.
        preferences: 偏好信息块.
    """

    head_url: str = Field(validation_alias="HeadUrl")
    nick_name: str = Field(validation_alias="NickName")
    signature: str = Field(validation_alias="Signature")
    encryption_account: str = Field(validation_alias="EncryptionAccount")
    preferences: dict[str, Any] = Field(validation_alias="Preferences")


class ListeningReport(Response):
    """用户听歌报告摘要.

    Attributes:
        report: 听歌报告分块列表.
    """

    report: list[dict[str, Any]] = Field(validation_alias="Report")


class UserMusicGeneResponse(Response):
    """用户音乐基因视图响应.

    Attributes:
        user_info_card: 用户卡片信息.
        listening_report: 听歌报告摘要.
        sort_array: 排序提示数组.
        is_visit_account: 是否访问本人账号.
    """

    user_info_card: UserInfoCard = Field(validation_alias="UserInfoCard")
    listening_report: ListeningReport = Field(validation_alias="ListeningReport")
    sort_array: list[int] = Field(validation_alias="SortArray")
    is_visit_account: bool = Field(validation_alias="IsVisitAccount")


class UserHomepageBaseInfo(Response):
    """用户主页头部基础信息.

    Attributes:
        encrypted_uin: 加密 UIN.
        name: 用户名.
        avatar: 头像地址.
        background_image: 背景图地址.
        user_type: 用户类型标记.
    """

    encrypted_uin: str = Field(validation_alias="EncryptedUin")
    name: str = Field(validation_alias="Name")
    avatar: str = Field(validation_alias="Avatar")
    background_image: str = Field(validation_alias="BackgroundImage")
    user_type: int = Field(validation_alias="UserType")


class UserHomepageResponse(Response):
    """用户主页视图响应.

    Attributes:
        base_info: 主页头部基础信息.
        singer: 主页关联歌手信息.
        is_followed: 当前账号是否已关注.
        tab_detail: 主页标签页附加信息.
    """

    base_info: UserHomepageBaseInfo = Field(json_schema_extra={"jsonpath": "$.Info.BaseInfo"})
    singer: dict[str, Any] = Field(json_schema_extra={"jsonpath": "$.Info.Singer"})
    is_followed: int = Field(json_schema_extra={"jsonpath": "$.Info.IsFollowed"})
    tab_detail: dict[str, Any] = Field(validation_alias="TabDetail")


class VipIdentity(Response):
    """VIP 信息响应中的会员身份明细块.

    Attributes:
        vip: 绿钻会员标志.
        huge_vip: 豪华绿钻会员标志.
        huge_vip_start: 豪华绿钻生效时间.
        huge_vip_end: 豪华绿钻到期时间.
        year_flag: 年费会员标志.
        huge_year_flag: 豪华年费会员标志.
        twelve: 十二平台会员标志.
        twelve_start: 十二平台会员生效时间.
        twelve_end: 十二平台会员到期时间.
        child_vip: 儿童会员标志.
        exp_vip: 体验会员标志.
        group_vip_flag: 家庭组会员标志.
        group_vip_start: 家庭组会员生效时间.
        group_vip_end: 家庭组会员到期时间.
        cp_lover_flag: 情侣会员标志.
        cp_lover_start: 情侣会员生效时间.
        cp_lover_end: 情侣会员到期时间.
        ad_vip_flag: 广告会员标志.
        eight: 八平台会员标志.
        eight_start: 八平台会员生效时间.
        eight_end: 八平台会员到期时间.
        level: 会员等级.
        next_level: 下一会员等级.
        icon: 官方等级徽章图地址.
        purchase_url: 会员购买页地址.
    """

    vip: int = 0
    huge_vip: int = Field(default=0, validation_alias="HugeVip")
    huge_vip_start: str = Field(default="", validation_alias="HugeVipStart")
    huge_vip_end: str = Field(default="", validation_alias="HugeVipEnd")
    year_flag: int = Field(default=0, validation_alias="yearflag")
    huge_year_flag: int = Field(default=0, validation_alias="HugeYearFlag")
    twelve: int = 0
    twelve_start: str = Field(default="", validation_alias="twelveStart")
    twelve_end: str = Field(default="", validation_alias="twelveEnd")
    child_vip: int = Field(default=0, validation_alias="ChildVip")
    exp_vip: int = Field(default=0, validation_alias="ExpVip")
    group_vip_flag: int = Field(default=0, validation_alias="GroupVipFlag")
    group_vip_start: str = Field(default="", validation_alias="GroupVipStart")
    group_vip_end: str = Field(default="", validation_alias="GroupVipEnd")
    cp_lover_flag: int = Field(default=0, validation_alias="CPLoverFlag")
    cp_lover_start: str = Field(default="", validation_alias="CPLoverStart")
    cp_lover_end: str = Field(default="", validation_alias="CPLoverEnd")
    ad_vip_flag: int = Field(default=0, validation_alias="AdVipFlag")
    eight: int = 0
    eight_start: str = Field(default="", validation_alias="eightStart")
    eight_end: str = Field(default="", validation_alias="eightEnd")
    level: int = 0
    next_level: int = Field(default=0, validation_alias="nextlevel")
    icon: str = ""
    purchase_url: str = Field(default="", validation_alias="purchaseUrl")


class VipUserInfo(Response):
    """VIP 信息响应中的用户权益摘要块.

    Attributes:
        buy_url: 开通入口地址.
        my_vip_url: 我的会员页地址.
        score: 会员积分.
        expire: 到期时间戳.
        music_level: 音乐等级.
    """

    buy_url: str = Field(default="", validation_alias=AliasChoices("buy_url", "buyurl"))
    my_vip_url: str = Field(default="", validation_alias=AliasChoices("my_vip_url", "myvipurl"))
    score: int = 0
    expire: int = 0
    music_level: int = Field(default=0, validation_alias="music_level")


class UserVipInfoResponse(Response):
    """VIP 信息视图响应.

    Attributes:
        auto_down: 自动下载开关状态.
        can_renew: 是否可续费.
        max_dir_num: 最大歌单数量.
        max_song_num: 最大歌曲数量.
        song_limit_msg: 歌曲上限提示文案.
        svip: 超级会员标志.
        star: 星级会员标志.
        star_start: 星级会员生效时间.
        star_end: 星级会员到期时间.
        ystar: 年费星级会员标志.
        ystar_start: 年费星级会员生效时间.
        ystar_end: 年费星级会员到期时间.
        identity: 会员身份明细.
        userinfo: 用户权益摘要.
    """

    auto_down: int = Field(default=0, validation_alias=AliasChoices("auto_down", "autoDown", "autodown"))
    can_renew: int = Field(default=0, validation_alias="canRenew")
    max_dir_num: int = Field(default=0, validation_alias=AliasChoices("max_dir_num", "maxDirNum", "maxdirnum"))
    max_song_num: int = Field(default=0, validation_alias=AliasChoices("max_song_num", "maxSongNum", "maxsongnum"))
    song_limit_msg: str = Field(default="", validation_alias=AliasChoices("song_limit_msg", "songLimitMsg"))
    svip: int = 0
    star: int = 0
    star_start: str = Field(default="", validation_alias="starstart")
    star_end: str = Field(default="", validation_alias="starend")
    ystar: int = 0
    ystar_start: str = Field(default="", validation_alias="ystarstart")
    ystar_end: str = Field(default="", validation_alias="ystarend")
    identity: VipIdentity = Field(default_factory=VipIdentity)
    userinfo: VipUserInfo = Field(default_factory=VipUserInfo)


class RelationUser(Response):
    """关注或粉丝列表中的单个用户条目.

    Attributes:
        mid: 用户 MID.
        enc_uin: 加密 UIN.
        name: 用户名称.
        desc: 描述文案.
        avatar_url: 头像地址.
        fan_num: 粉丝数.
        is_follow: 当前账号是否已关注.
    """

    mid: str = Field(validation_alias="MID")
    enc_uin: str = Field(validation_alias="EncUin")
    name: str = Field(validation_alias="Name")
    desc: str = Field(validation_alias="Desc")
    avatar_url: str = Field(validation_alias="AvatarUrl")
    fan_num: int = Field(validation_alias="FanNum")
    is_follow: bool = Field(validation_alias="IsFollow")


class UserRelationListResponse(Response):
    """关注关系分页列表响应.

    Attributes:
        total: 总数量.
        users: 当前页用户列表.
        has_more: 是否还有更多结果.
        last_pos: 下一页游标.
        msg: 附加消息.
        lock_flag: 锁定状态标记.
        lock_msg: 锁定提示文案.
    """

    total: int = Field(default=0, validation_alias="Total")
    users: list[RelationUser] = Field(default_factory=list, json_schema_extra={"jsonpath": "$.List[*]"})
    has_more: bool = Field(default=False, validation_alias="HasMore")
    last_pos: str = Field(default="", validation_alias="LastPos")
    msg: str = Field(default="", validation_alias="Msg")
    lock_flag: int = Field(default=0, validation_alias="LockFlag")
    lock_msg: str = Field(default="", validation_alias="LockMsg")


class FriendEntry(Response):
    """好友列表中的单个好友条目.

    Attributes:
        encrypt_uin: 加密 UIN.
        user_name: 用户名.
        avatar_url: 头像地址.
        is_follow: 当前账号是否已关注.
    """

    encrypt_uin: str = Field(validation_alias="EncryptUin")
    user_name: str = Field(validation_alias="UserName")
    avatar_url: str = Field(validation_alias="AvatarUrl")
    is_follow: bool = Field(validation_alias="IsFollow")


class UserFriendListResponse(Response):
    """好友列表视图响应.

    Attributes:
        friends: 当前页好友列表.
        has_more: 是否还有更多结果.
    """

    friends: list[FriendEntry] = Field(validation_alias="Friends")
    has_more: bool = Field(validation_alias="HasMore")


class UserFavMvItem(MV):
    """用户收藏 MV 列表中的单个条目.

    Attributes:
        id: MV ID.
        vid: MV VID.
        name: MV 名称.
        title: MV 标题.
        picurl: MV 封面地址.
        playcount: 播放量.
        publish_date: 发布时间.
        singer_id: 歌手 ID.
        singer_mid: 歌手 MID.
        singer_name: 歌手名称.
        status: 状态标记.
    """

    picurl: str = Field(validation_alias="picUrl")
    playcount: int
    publish_date: int
    singer_id: int = Field(validation_alias="singerId")
    singer_mid: str = Field(validation_alias="singerMid")
    singer_name: str = Field(validation_alias="singerName")
    status: int


class UserFavMvResponse(Response):
    """用户收藏 MV 列表视图响应.

    Attributes:
        code: 返回码.
        sub_code: 子返回码.
        msg: 附加消息.
        mv_list: 当前页收藏 MV 列表.
    """

    code: int
    sub_code: int = Field(validation_alias=AliasChoices("subCode", "subcode"))
    msg: str
    mv_list: list[UserFavMvItem] = Field(validation_alias="mvlist")


class DislikeItem(BaseModel):
    """不喜欢列表中的单个条目.

    Attributes:
        id:     不喜欢实体的 ID (歌手ID、歌曲ID等).
        name:   不喜欢实体的名称.
        img:    不喜欢实体的图片/封面 URL.
        id_type: 实体类型标识.
        time:   添加到不喜欢列表的时间戳.
    """

    id: str = Field(validation_alias="ID")
    name: str = Field(validation_alias="Name")
    img: str = Field(default="", validation_alias="Img")
    id_type: int = Field(validation_alias="IdType")
    time: int = Field(validation_alias="Time")


class DislikeListData(Response):
    """GetDislikeList 响应数据.

    Attributes:
        retcode: 业务返回码.
        msg:     业务返回信息.
        singers: 不喜欢的歌手列表.
        songs:   不喜欢的歌曲列表.
        styles:  不喜欢的风格/流派列表.
        page:    当前页码.
        token:   翻页 Token.
    """

    retcode: int = Field(validation_alias="Retcode")
    msg: str = Field(default="", validation_alias="Msg")
    singers: list[DislikeItem] = Field(default_factory=list, validation_alias="Singers")
    songs: list[DislikeItem] = Field(default_factory=list, validation_alias="Songs")
    styles: list[DislikeItem] = Field(default_factory=list, validation_alias="Styles")
    page: int = Field(validation_alias="Page")
    token: str = Field(default="", validation_alias="Token")
