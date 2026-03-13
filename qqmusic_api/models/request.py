"""基础数据模型模块."""

from typing import Any, TypeAlias, TypedDict, TypeVar

from pydantic import BaseModel, Field
from tarsio import Struct, TarsDict, field


class CommonParams(BaseModel, frozen=True):
    """通用请求参数."""

    # 客户端类型
    ct: int = Field()
    # 版本号
    cv: int = Field()
    v: int | None = Field(default=None)
    # 平台标识
    platform: str | None = Field(default=None)
    # App ID
    tme_app_id: str = Field(default="qqmusic", alias="tmeAppID")
    # 渠道 ID
    chid: str = Field(default="0")
    # 通用账号标识
    uin: int | None = Field(default=None)
    # [Web/Desktop] CSRF Token
    g_tk: int | None = Field(default=None)
    g_tk_new: int | None = Field(default=None, alias="g_tk_new_20200303")
    # [App] 核心登录态 & QQ互联
    qq: str | None = Field(default=None)
    authst: str | None = Field(default=None)
    tme_login_type: int | None = Field(default=None, alias="tmeLoginType")
    # [App] Android 核心指纹
    qimei: str | None = Field(default=None, alias="QIMEI")
    qimei36: str | None = Field(default=None, alias="QIMEI36")
    # [App] 硬件标识
    open_udid: str | None = Field(default=None, alias="OpenUDID")
    open_udid2: str | None = Field(default=None, alias="OpenUDID2")
    udid: str | None = Field(default=None)
    aid: str | None = Field(default=None)
    guid: str | None = Field(default=None)
    os_ver: str | None = Field(default=None)
    phonetype: str | None = Field(default=None)
    devicelevel: str | None = Field(default=None)
    newdevicelevel: str | None = Field(default=None)
    rom: str | None = Field(default=None)
    nettype: str = Field(default="1030")
    format: str = "json"
    in_charset: str = Field(default="utf-8", alias="inCharset")
    out_charset: str = Field(default="utf-8", alias="outCharset")
    notice: int = 0
    need_new_code: int = Field(default=1, alias="needNewCode")


class Credential(BaseModel, frozen=True):
    """凭据类.

    Attributes:
        openid:        OpenID
        refresh_token: RefreshToken
        access_token:  AccessToken
        expired_at:    到期时间
        musicid:       QQMusicID
        musickey:      QQMusicKey
        unionid:       UnionID
        str_musicid:   QQMusicID
        refresh_key:   RefreshKey
        login_type:    登录类型
    """

    openid: str = ""
    refresh_token: str = ""
    access_token: str = ""
    expired_at: int = 0
    musicid: int = 0
    musickey: str = ""
    unionid: str = ""
    str_musicid: str = ""
    refresh_key: str = ""
    musickey_create_time: int = Field(default=0, alias="musickeyCreateTime")
    key_expires_in: int = Field(default=0, alias="keyExpiresIn")
    first_login: int = Field(default=0)
    bind_account_type: int = Field(default=0, alias="bindAccountType")
    need_refresh_key_in: int = Field(default=0, alias="needRefreshKeyIn")
    encrypt_uin: str = Field(default="", alias="encryptUin")
    login_type: int = Field(default=0, alias="loginType")


class RequestItem(TypedDict):
    """请求项."""

    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]


class JceRequestItem(Struct):
    """JCE 请求项."""

    module: str = field(tag=0)
    method: str = field(tag=1)
    param: TarsDict = field(tag=2, wrap_simplelist=True)


class JceRequest(Struct):
    """JCE 请求体."""

    comm: dict[str, Any] = field(tag=0)
    data: dict[str, JceRequestItem] = field(tag=1)


ResponseData: TypeAlias = dict[str, Any] | TarsDict
RequestValue: TypeAlias = BaseModel | ResponseData
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
RequestResult = TypeVar("RequestResult", bound=RequestValue)


class JceResponseItem(Struct):
    """JCE 格式响应项."""

    code: int = field(tag=0, default=0)
    data: TarsDict = field(tag=3, default_factory=TarsDict, wrap_simplelist=True)


class JceResponse(Struct):
    """JCE 格式 API 响应."""

    code: int = field(tag=0, default=0)
    data: dict[str, JceResponseItem] = field(tag=4, default_factory=dict)
