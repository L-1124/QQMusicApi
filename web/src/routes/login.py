"""登录 Web 路由契约."""

from qqmusic_api import Credential

from ..modules.login import (
    PhoneAuthCodeData,
    QRCodeData,
    QRCodeStatusData,
    WebQRLoginType,
    check_expired_adapter,
    phone_authcode_adapter,
    phone_authorize_adapter,
    qrcode_adapter,
    qrcode_status_adapter,
    refresh_credential_adapter,
)
from ..routing.route_types import AuthPolicy, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "login",
        "check_expired",
        "/login/check_expired",
        bool,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        adapter=check_expired_adapter,
    ),
    R(
        "login",
        "refresh_credential",
        "/login/refresh_credential",
        Credential,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        adapter=refresh_credential_adapter,
    ),
    R(
        "login",
        "qrcode",
        "/login/qrcode/{login_type}",
        QRCodeData,
        params=(P("login_type", WebQRLoginType, "二维码登录类型."),),
        adapter=qrcode_adapter,
    ),
    R(
        "login",
        "qrcode_status",
        "/login/qrcode/{login_type}/status",
        QRCodeStatusData,
        params=(
            P("login_type", WebQRLoginType, "二维码登录类型."),
            Q("identifier", str, description="二维码标识符."),
        ),
        adapter=qrcode_status_adapter,
    ),
    R(
        "login",
        "phone_authcode",
        "/login/phone/authcode",
        PhoneAuthCodeData,
        params=(
            Q("phone", int | None, None, "明文手机号."),
            Q("encrypted_phone", str | None, None, "加密手机号."),
            Q("country_code", int, 86, "国家代码."),
        ),
        adapter=phone_authcode_adapter,
    ),
    R(
        "login",
        "phone_authorize",
        "/login/phone/authorize",
        Credential,
        params=(
            Q("auth_code", str, description="短信验证码 (字符串, 保留前导零)."),
            Q("phone", int | None, None, "明文手机号."),
            Q("encrypted_phone", str | None, None, "加密手机号."),
        ),
        adapter=phone_authorize_adapter,
    ),
)
