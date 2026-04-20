"""请求版本策略中心."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..models.request import CommonParams, Credential
from ..utils.common import hash33
from ..utils.device import Device


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
    qimei_app_version: str | None = None
    qimei_sdk_version: str | None = None


@dataclass(slots=True)
class VersionPolicy:
    """请求版本策略."""

    android: VersionProfile
    desktop: VersionProfile
    web: VersionProfile
    _comm_cache: dict[tuple, dict[str, Any]] = field(
        init=False,
        default_factory=dict,
        repr=False,
        compare=False,
    )

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
        device: Device,
        qimei: dict[str, str] | None,
        guid: str,
    ) -> dict[str, Any]:
        """构建统一 comm 参数.

        Args:
            platform: 平台枚举.
            credential: 登录凭证.
            device: 设备信息.
            qimei: QIMEI 缓存.
            guid: 客户端 GUID.

        Returns:
            构建后的 comm 参数字典.
        """
        cache_key = (
            platform,
            credential,
            (
                device.android_id,
                device.version.release,
                device.model,
                device.version.sdk,
                device.fingerprint,
            )
            if platform == Platform.ANDROID
            else (),
            tuple(sorted(qimei.items())) if qimei else None,
            guid,
        )
        cached = self._comm_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        profile = self.get_profile(platform)
        if platform == Platform.ANDROID:
            params = CommonParams(
                ct=profile.ct,
                cv=profile.cv,
                v=profile.v,
                chid="10003505",
                qq=str(credential.musicid) if credential.musicid else None,
                authst=credential.musickey or None,
                tmeAppID="qqmusic",
                tmeLoginType=credential.login_type,
                QIMEI=qimei["q16"] if qimei is not None else "",
                QIMEI36=qimei["q36"] if qimei is not None else "",
                OpenUDID=guid,
                udid=guid,
                OpenUDID2=guid,
                aid=device.android_id,
                os_ver=device.version.release,
                phonetype=device.model,
                devicelevel=str(device.version.sdk),
                newdevicelevel=str(device.version.sdk),
                rom=device.fingerprint,
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
                in_charset="utf-8",
                out_charset="utf-8",
                notice=0,
                need_new_code=1,
            )

        comm = params.model_dump(by_alias=True, exclude_none=True)

        self._comm_cache[cache_key] = comm
        return comm.copy()

    def build_query_params(self, platform: Platform) -> dict[str, int]:
        """构建查询接口通用参数.

        Args:
            platform: 平台枚举.

        Returns:
            查询参数中的通用版本字段.
        """
        profile = self.get_profile(platform)
        return {"ct": profile.ct, "cv": profile.cv}

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

    def get_qimei_app_version(self) -> str:
        """获取 QIMEI 请求 appVersion.

        Returns:
            QIMEI appVersion.
        """
        profile = self.get_profile(Platform.ANDROID)
        return profile.qimei_app_version or "14.9.0.8"

    def get_qimei_sdk_version(self) -> str:
        """获取 QIMEI 请求 sdkVersion.

        Returns:
            QIMEI sdkVersion.
        """
        profile = self.get_profile(Platform.ANDROID)
        return profile.qimei_sdk_version or "1.2.13.6"

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
