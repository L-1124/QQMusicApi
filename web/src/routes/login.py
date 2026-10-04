"""登录 Web 路由契约."""

from qqmusic_api import Credential

from ..modules.login import (
    PhoneAuthCodeData,
    QRCodeData,
    QRCodeStatusData,
    WebQRLoginType,
)
from ..routing.route_types import AuthPolicy, HttpMethod, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "login",
        "check_expired",
        "/login/check_expired",
        bool,
        auth=AuthPolicy.OPTIONAL,
    ),
    R(
        "login",
        "refresh_credential",
        "/login/refresh_credential",
        Credential,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "login",
        "qrcode",
        "/login/qrcode/{login_type}",
        QRCodeData,
        params=(P("login_type", WebQRLoginType, "二维码登录类型."),),
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
    ),
    R(
        "login",
        "phone_authcode",
        "/login/phone/authcode",
        PhoneAuthCodeData,
        methods=(HttpMethod.POST,),
        params=(
            Q("phone", int | None, None, "明文手机号."),
            Q("encrypted_phone", str | None, None, "加密手机号."),
            Q("country_code", int, 86, "国家代码."),
        ),
    ),
    R(
        "login",
        "phone_authorize",
        "/login/phone/authorize",
        Credential,
        methods=(HttpMethod.POST,),
        params=(
            Q("auth_code", str, description="短信验证码 (字符串, 保留前导零)."),
            Q("phone", int | None, None, "明文手机号."),
            Q("encrypted_phone", str | None, None, "加密手机号."),
        ),
    ),
)
