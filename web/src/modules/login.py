"""登录模块 Web 路由适配."""

import base64
from enum import Enum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator

from qqmusic_api import Credential
from qqmusic_api.models.login import (
    QR,
    PhoneAuthCodeResult,
    PhoneLoginEvents,
    QRCodeLoginEvents,
    QRLoginResult,
    QRLoginType,
)
from web.src.routing.params import path_enum_value
from web.src.routing.route_types import RouteContext


class WebQRLoginType(str, Enum):
    """Web 层支持的二维码登录类型."""

    QQ = "qq"
    WX = "wx"


WEB_QR_LOGIN_TYPES = {WebQRLoginType.QQ: QRLoginType.QQ, WebQRLoginType.WX: QRLoginType.WX}
WEB_QR_LOGIN_TYPE_DESCRIPTION = "二维码登录类型. 当前 Web 层仅支持 `qq` / `wx`."


class QRCodeData(BaseModel):
    """二维码响应数据."""

    qr_type: str = Field(description="二维码登录类型名称.")
    identifier: str = Field(description="二维码标识符.")
    mimetype: str = Field(description="二维码 MIME 类型.")
    data: str = Field(description="二维码图片的 Base64 编码内容.")
    img: str = Field(description="可直接用于前端 img src 的 Data URL.")


class QRCodeStatusData(BaseModel):
    """二维码登录状态数据."""

    event: int = Field(
        description=(
            """
            二维码登录状态码
            - DONE=0: 登录成功
            - SCAN=1: 二维码等待扫描
            - CONF=2: 二维码等待确认
            - TIMEOUT=3: 二维码已超时
            - REFUSE=4: 二维码已被拒绝
            - OTHER=-1: 其他错误
        """
        ),
        json_schema_extra={"enum": [-1, 0, 1, 2, 3, 4]},
    )
    done: bool = Field(description="当前事件是否表示流程结束.")
    credential: Credential | None = Field(default=None, description="登录完成时返回的凭证.")
    identifier: str = Field(description="二维码标识符.")
    login_type: str = Field(description="二维码登录类型名称.")


class PhoneAuthCodeData(BaseModel):
    """手机验证码发送结果数据."""

    event: int = Field(
        description=(
            """
            验证码发送状态码
            - SEND=0: 验证码已发送
            - CAPTCHA=1: 需要滑块验证
            - FREQUENCY=2: 发送过于频繁
            - OTHER=-1: 其他错误
        """
        ),
        json_schema_extra={"enum": [-1, 0, 1, 2]},
    )
    info: str | None = Field(default=None, description="附加说明信息.")


class PhoneTargetRequest(BaseModel):
    """手机号目标请求体基类."""

    phone: int | None = Field(default=None, description="明文手机号.")
    encrypted_phone: str | None = Field(default=None, description="加密手机号.")

    @model_validator(mode="after")
    def _validate_phone_target(self) -> "PhoneTargetRequest":
        """校验手机号输入只能提供一种形式."""
        if (self.phone is None) == (self.encrypted_phone is None):
            raise ValueError("phone 与 encrypted_phone 必须且只能提供一个")
        return self

    def phone_value(self) -> int | str:
        """返回 modules 层所需的手机号输入值."""
        if self.encrypted_phone is not None:
            return self.encrypted_phone
        if self.phone is None:
            raise ValueError("缺少手机号输入")
        return self.phone


class SendAuthcodeRequest(PhoneTargetRequest):
    """发送手机验证码请求体."""

    country_code: int = Field(default=86, description="国家代码.")


class PhoneAuthorizeRequest(PhoneTargetRequest):
    """手机验证码鉴权请求体."""

    auth_code: str = Field(description="短信验证码 (字符串, 保留前导零).")


QR_CODE_EVENT_CODES = {
    QRCodeLoginEvents.DONE: 0,
    QRCodeLoginEvents.SCAN: 1,
    QRCodeLoginEvents.CONF: 2,
    QRCodeLoginEvents.TIMEOUT: 3,
    QRCodeLoginEvents.REFUSE: 4,
}
PHONE_EVENT_CODES = {
    PhoneLoginEvents.SEND: 0,
    PhoneLoginEvents.CAPTCHA: 1,
    PhoneLoginEvents.FREQUENCY: 2,
}


def _validate_web_qr_login_type(login_type: WebQRLoginType) -> QRLoginType:
    """校验并转换 Web 层支持的二维码登录类型."""
    try:
        return WEB_QR_LOGIN_TYPES[login_type]
    except KeyError as exc:
        allowed = ", ".join(path_enum_value(item) for item in WEB_QR_LOGIN_TYPES)
        raise HTTPException(status_code=422, detail=f"Web 层暂不支持该二维码登录类型. 可选值: {allowed}") from exc


def _serialize_qrcode(qrcode: QR) -> QRCodeData:
    """序列化二维码对象为 Web 响应数据."""
    data = base64.b64encode(qrcode.data).decode("ascii")
    return QRCodeData(
        qr_type=path_enum_value(qrcode.qr_type),
        identifier=qrcode.identifier,
        mimetype=qrcode.mimetype,
        data=data,
        img=f"data:{qrcode.mimetype};base64,{data}",
    )


def _serialize_qrcode_status(result: QRLoginResult, qrcode: QR) -> QRCodeStatusData:
    """序列化二维码登录状态结果."""
    return QRCodeStatusData(
        event=QR_CODE_EVENT_CODES.get(result.event, -1),
        done=result.done,
        credential=result.credential,
        identifier=qrcode.identifier,
        login_type=path_enum_value(qrcode.qr_type),
    )


def _serialize_phone_authcode(result: PhoneAuthCodeResult) -> PhoneAuthCodeData:
    """序列化手机验证码发送结果."""
    event_code = PHONE_EVENT_CODES.get(result.event, -1)
    return PhoneAuthCodeData(event=event_code, info=result.info)


def _build_qrcode_placeholder(identifier: str, login_type: QRLoginType) -> QR:
    """为二维码续接模式构造最小占位二维码对象."""
    return QR(data=b"", qr_type=login_type, mimetype="image/png", identifier=identifier)


async def check_expired_adapter(context: RouteContext) -> bool:
    """检查登录凭证是否过期."""
    return await context.client.login.check_expired(context.params["credential"])


async def refresh_credential_adapter(context: RouteContext) -> Credential:
    """刷新登录凭证."""
    return await context.client.login.refresh_credential(context.params["credential"])


async def qrcode_adapter(context: RouteContext) -> QRCodeData:
    """获取登录二维码."""
    login_type = _validate_web_qr_login_type(context.params["login_type"])
    qrcode = await context.client.login.get_qrcode(login_type)
    return _serialize_qrcode(qrcode)


async def qrcode_status_adapter(context: RouteContext) -> QRCodeStatusData:
    """检查二维码登录状态."""
    login_type = _validate_web_qr_login_type(context.params["login_type"])
    qrcode = _build_qrcode_placeholder(context.params["identifier"], login_type)
    result = await context.client.login.check_qrcode(qrcode)
    return _serialize_qrcode_status(result, qrcode)


async def phone_authcode_adapter(context: RouteContext) -> PhoneAuthCodeData:
    """发送手机验证码."""
    query = _validate_model(SendAuthcodeRequest, dict(context.params))
    result = await context.client.login.send_authcode(query.phone_value(), query.country_code)
    return _serialize_phone_authcode(result)


async def phone_authorize_adapter(context: RouteContext) -> Credential:
    """使用手机验证码登录."""
    query = _validate_model(PhoneAuthorizeRequest, dict(context.params))
    return await context.client.login.phone_authorize(query.phone_value(), query.auth_code)


def _validate_model(model_type: type[BaseModel], data: dict[str, Any]) -> Any:
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
