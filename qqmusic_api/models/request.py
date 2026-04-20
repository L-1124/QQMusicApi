"""基础数据模型模块."""

from typing import Any, TypedDict

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, model_validator
from tarsio import Struct, TarsDict, field


class BaseModel(PydanticBaseModel):
    """基础数据模型."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore", frozen=True)


class CommonParams(BaseModel):
    """通用请求参数."""

    # 客户端类型
    ct: int = Field()
    # 版本号
    cv: int = Field()
    v: int | None = Field(default=None)
    # 平台标识
    platform: str | None = Field(default=None)
    # App ID
    tme_app_id: str | None = Field(default=None, alias="tmeAppID")
    # 渠道 ID
    chid: str | None = Field(default=None)
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
    format: str | None = Field(default=None)
    in_charset: str | None = Field(default=None, alias="inCharset")
    out_charset: str | None = Field(default=None, alias="outCharset")
    # [Web] 通知开关
    notice: int | None = Field(default=None)
    # [Web] 新设备码开关
    need_new_code: int | None = Field(default=None)


class Credential(BaseModel):
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

    @model_validator(mode="before")
    @classmethod
    def _infer_login_type(cls, data: Any) -> Any:
        """在缺省时根据 musickey 推断登录类型."""
        if not isinstance(data, dict):
            return data

        if data.get("loginType") or data.get("login_type"):
            return data

        musickey = data.get("musickey", "")
        inferred_login_type = 1 if isinstance(musickey, str) and musickey.startswith("W_X") else 2
        return {**data, "loginType": inferred_login_type}

    def is_expired(self) -> bool:
        """检查凭据是否过期."""
        import time

        current_time = int(time.time())
        return current_time >= self.musickey_create_time + self.key_expires_in


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


class JceResponseItem(Struct):
    """JCE 格式响应项."""

    code: int = field(tag=0, default=0)
    data: TarsDict = field(tag=3, default_factory=TarsDict, wrap_simplelist=True)


class JceResponse(Struct):
    """JCE 格式 API 响应."""

    code: int = field(tag=0, default=0)
    data: dict[str, JceResponseItem] = field(tag=4, default_factory=dict)


class Response(BaseModel):
    """API 响应基类."""

    @model_validator(mode="before")
    @classmethod
    def _extract_jsonpath_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        processed_data = data.copy()

        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra

            if isinstance(extra, dict) and "jsonpath" in extra:
                jsonpath_expr_str = str(extra["jsonpath"])
                target_key = field_info.alias or field_name

                from ..utils import parse_jsonpath

                jsonpath_expr = parse_jsonpath(jsonpath_expr_str)
                matches = jsonpath_expr.find(data)

                if matches:
                    if len(matches) == 1:
                        processed_data[target_key] = matches[0].value
                    else:
                        processed_data[target_key] = [match.value for match in matches]

        return processed_data
