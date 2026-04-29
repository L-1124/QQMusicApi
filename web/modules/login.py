"""登录模块 Web 路由适配."""

import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, model_validator

from qqmusic_api import Client, Credential
from qqmusic_api.models.login import (
    QR,
    PhoneAuthCodeResult,
    PhoneLoginEvents,
    QRCodeLoginEvents,
    QRLoginResult,
    QRLoginType,
)
from web.auth import credential_from_cookies
from web.deps import client_dependency
from web.enum_utils import coerce_enum_value
from web.response import ApiResponse, success_response
from web.schema import COOKIE_SECURITY_REQUIREMENT

router = APIRouter(prefix="/login", tags=["login"])
credential_dependency = Depends(credential_from_cookies)
WEB_QR_LOGIN_TYPE_DESCRIPTION = "二维码登录类型. 当前 Web 层仅支持 `QQ` / `WX`, 暂不支持 `MOBILE`."


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

    auth_code: int = Field(description="短信验证码.")


QR_CODE_EVENT_CODES = {
    QRCodeLoginEvents.DONE: 0,
    QRCodeLoginEvents.SCAN: 1,
    QRCodeLoginEvents.CONF: 2,
    QRCodeLoginEvents.TIMEOUT: 3,
    QRCodeLoginEvents.REFUSE: 4,
    QRCodeLoginEvents.OTHER: -1,
}
PHONE_EVENT_CODES = {
    PhoneLoginEvents.SEND: 0,
    PhoneLoginEvents.CAPTCHA: 1,
    PhoneLoginEvents.FREQUENCY: 2,
    PhoneLoginEvents.OTHER: -1,
}


def _parse_web_qr_login_type(value: str) -> QRLoginType:
    """解析 Web 层支持的二维码登录类型参数."""
    try:
        login_type = coerce_enum_value(value, QRLoginType)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"未知二维码登录类型: {value}") from exc
    if login_type not in {QRLoginType.QQ, QRLoginType.WX}:
        raise HTTPException(status_code=422, detail="Web 层暂不支持 MOBILE 二维码登录")
    return login_type


def _serialize_qrcode(qrcode: QR) -> QRCodeData:
    """序列化二维码对象为 Web 响应数据."""
    data = base64.b64encode(qrcode.data).decode("ascii")
    return QRCodeData(
        qr_type=qrcode.qr_type.name,
        identifier=qrcode.identifier,
        mimetype=qrcode.mimetype,
        data=data,
        img=f"data:{qrcode.mimetype};base64,{data}",
    )


def _serialize_qrcode_status(result: QRLoginResult, qrcode: QR) -> QRCodeStatusData:
    """序列化二维码登录状态结果."""
    return QRCodeStatusData(
        event=QR_CODE_EVENT_CODES.get(result.event, QR_CODE_EVENT_CODES[QRCodeLoginEvents.OTHER]),
        done=result.done,
        credential=result.credential,
        identifier=qrcode.identifier,
        login_type=qrcode.qr_type.name,
    )


def _serialize_phone_authcode(result: PhoneAuthCodeResult) -> PhoneAuthCodeData:
    """序列化手机验证码发送结果."""
    event_code = PHONE_EVENT_CODES.get(result.event, -1)
    return PhoneAuthCodeData(event=event_code, info=result.info)


def _build_qrcode_placeholder(identifier: str, login_type: QRLoginType) -> QR:
    """为二维码续接模式构造最小占位二维码对象."""
    return QR(data=b"", qr_type=login_type, mimetype="image/png", identifier=identifier)


@router.get(
    "/check_expired",
    summary="检查登录凭证是否过期",
    description="检查当前请求可用的登录凭证是否过期.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def login_check_expired(
    client: Client = client_dependency,
    credential: Credential = credential_dependency,
):
    """检查登录凭证是否过期."""
    return success_response(await client.login.check_expired(credential))


@router.get(
    "/refresh_credential",
    summary="刷新登录凭证",
    description="刷新当前请求可用的登录凭证并返回新凭证.",
    response_model=ApiResponse,
    openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]},
)
async def login_refresh_credential(
    client: Client = client_dependency,
    credential: Credential = credential_dependency,
):
    """刷新登录凭证."""
    return success_response(await client.login.refresh_credential(credential))


@router.get(
    "/qrcode",
    summary="获取登录二维码",
    description="获取指定类型的登录二维码.",
    response_model=ApiResponse,
)
async def login_get_qrcode(
    login_type: str = Query(description=WEB_QR_LOGIN_TYPE_DESCRIPTION, json_schema_extra={"enum": ["QQ", "WX"]}),
    client: Client = client_dependency,
):
    """获取登录二维码."""
    qrcode = await client.login.get_qrcode(_parse_web_qr_login_type(login_type))
    return success_response(_serialize_qrcode(qrcode))


@router.get(
    "/qrcode/status",
    summary="检查二维码登录状态",
    description="根据二维码标识符与登录类型检查二维码登录状态.",
    response_model=ApiResponse,
)
async def login_check_qrcode(
    identifier: str = Query(description="二维码标识符."),
    login_type: str = Query(description=WEB_QR_LOGIN_TYPE_DESCRIPTION, json_schema_extra={"enum": ["QQ", "WX"]}),
    client: Client = client_dependency,
):
    """检查二维码登录状态."""
    parsed_login_type = _parse_web_qr_login_type(login_type)
    qrcode = _build_qrcode_placeholder(identifier, parsed_login_type)
    result = await client.login.check_qrcode(qrcode)
    return success_response(_serialize_qrcode_status(result, qrcode))


@router.get(
    "/phone/authcode",
    summary="发送手机验证码",
    description="向明文手机号或加密手机号发送登录验证码.",
    response_model=ApiResponse,
)
async def login_send_authcode(
    phone: int | None = Query(default=None, description="明文手机号."),
    encrypted_phone: str | None = Query(default=None, description="加密手机号."),
    country_code: int = Query(default=86, description="国家代码."),
    client: Client = client_dependency,
):
    """发送手机验证码."""
    try:
        query = SendAuthcodeRequest(phone=phone, encrypted_phone=encrypted_phone, country_code=country_code)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    result = await client.login.send_authcode(query.phone_value(), query.country_code)
    return success_response(_serialize_phone_authcode(result))


@router.get(
    "/phone/authorize",
    summary="使用手机验证码登录",
    description="使用明文手机号或加密手机号与短信验证码完成登录.",
    response_model=ApiResponse,
)
async def login_phone_authorize(
    auth_code: int = Query(description="短信验证码."),
    phone: int | None = Query(default=None, description="明文手机号."),
    encrypted_phone: str | None = Query(default=None, description="加密手机号."),
    client: Client = client_dependency,
):
    """使用手机验证码登录."""
    try:
        query = PhoneAuthorizeRequest(phone=phone, encrypted_phone=encrypted_phone, auth_code=auth_code)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return success_response(await client.login.phone_authorize(query.phone_value(), query.auth_code))
