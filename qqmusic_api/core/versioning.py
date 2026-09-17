"""请求版本策略中心."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from ..models.request import CommonParams, Credential

if TYPE_CHECKING:
    from ..utils.android_session import AndroidSession


class Platform(str, Enum):
    """请求平台枚举."""

    ANDROID = "android"
    DESKTOP = "desktop"
    WEB = "web"


@dataclass(frozen=True, slots=True)
class VersionProfile:
    """平台版本档案."""

    ct: int
    cv: int
    v: int | None = None
    platform: str | None = None
    ua_version: int | None = None
    qimei_app_version: str = "14.9.0.8"
    qimei_sdk_version: str = "1.2.13.6"


from ..utils.common import hash33
from ..utils.device import Device


@dataclass(slots=True)
class VersionPolicy:
    """请求版本策略.

    版本策略在 RequestEngine 生命周期内固定; 公参按次生成, 不持有
    全局可变缓存.
    """

    android: VersionProfile
    desktop: VersionProfile
    web: VersionProfile

    def get_profile(self, platform: Platform) -> VersionProfile:
        """获取平台对应的版本档案.

        Args:
            platform: 平台枚举.

        Returns:
            对应的版本档案.
        """
        if platform == Platform.ANDROID:
            return self.android
        if platform == Platform.DESKTOP:
            return self.desktop
        return self.web

    def build_comm(
        self,
        platform: Platform,
        credential: Credential,
        device: "Device",
        qimei: Mapping[str, str] | None,
        guid: str,
        session: "AndroidSession | None" = None,
    ) -> dict[str, str]:
        """构建统一 comm 参数.

        Args:
            platform: 平台枚举.
            credential: 登录凭证.
            device: 设备信息.
            qimei: QIMEI 缓存.
            guid: 客户端 GUID.
            session: Android 会话值 (AndroidSession); 仅 ANDROID 平台使用,
                显式注入而非读取设备共享会话槽.

        Returns:
            值均已转换为字符串的 comm 参数字典.
        """
        profile = self.get_profile(platform)
        if platform == Platform.ANDROID:
            session_uid = getattr(session, "uid", None)
            session_sid = getattr(session, "sid", None)
            params = CommonParams(
                ct=profile.ct,
                cv=profile.cv,
                v=profile.v,
                chid="10003505",
                qq=str(credential.musicid) if credential.musicid else None,
                authst=credential.musickey or None,
                tmeAppID="qqmusic",
                tmeLoginType=credential.login_type or None,
                QIMEI36=qimei["q36"] if qimei is not None else "",
                OpenUDID=guid,
                udid=guid,
                uid=session_uid,
                OpenUDID2=device.open_udid2,
                sid=session_sid,
                aid=device.android_id,
                os_ver=device.version.release,
                phonetype=escape(device.model, {'"': "&quot;"}),
            )
        elif platform == Platform.DESKTOP:
            params = CommonParams(
                ct=profile.ct,
                cv=profile.cv,
                platform=profile.platform,
                chid="0",
                uin=credential.musicid or None,
                g_tk=self.get_g_tk(credential),
                guid=guid.upper(),
            )
        else:
            g_tk = self.get_g_tk(credential)
            params = CommonParams(
                ct=profile.ct,
                cv=profile.cv,
                platform=profile.platform,
                chid="0",
                uin=credential.musicid,
                g_tk=g_tk,
                g_tk_new_20200303=g_tk,
                format="json",
                inCharset="utf-8",
                outCharset="utf-8",
                notice=0,
                need_new_code=1,
            )

        return {key: str(value) for key, value in params.model_dump(by_alias=True, exclude_none=True).items()}

    def get_user_agent(self, platform: Platform, device: Device) -> str:
        """根据平台获取 UA.

        Args:
            platform: 平台枚举.
            device: 设备信息.

        Returns:
            UA 字符串.
        """
        profile = self.get_profile(platform)
        if platform == Platform.ANDROID:
            ua_version = profile.ua_version or profile.cv
            return f"QQMusic {ua_version}(android {device.version.release})"
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    @staticmethod
    def get_g_tk(credential: Credential) -> int:
        """计算 g_tk.

        Args:
            credential: 登录凭证.

        Returns:
            计算后的 g_tk.
        """
        if credential.musickey:
            return hash33(credential.musickey, 5381)
        return 5381


DEFAULT_VERSION_POLICY = VersionPolicy(
    android=VersionProfile(
        ct=11,
        cv=14090008,
        v=14090008,
        ua_version=14090008,
        qimei_app_version="14.9.0.8",
        qimei_sdk_version="1.2.13.6",
    ),
    desktop=VersionProfile(
        ct=19,
        cv=2201,
    ),
    web=VersionProfile(
        ct=24,
        cv=4747474,
        platform="yqq.json",
    ),
)
