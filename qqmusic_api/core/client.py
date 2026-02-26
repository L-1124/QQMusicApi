"""Client"""

import logging
import sys
import uuid
from http.cookiejar import CookieJar
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar, cast

from typing_extensions import override

if sys.version_info >= (3, 11):
    from typing import Unpack
else:
    from typing_extensions import Unpack


import anyio
import httpx
import orjson as json
from pydantic import BaseModel
from tarsio import Struct, TarsDict

from ..models import (
    Credential,
    JceRequest,
    JceRequestItem,
    JceResponse,
    JsonRequest,
    JsonRequestItem,
    JsonResponse,
)
from ..utils.common import bool_to_int
from ..utils.device import Device
from ..utils.qimei import QimeiResult, get_qimei
from .exceptions import ApiError, HTTPError, NetworkError, build_api_error, extract_api_error_code
from .versioning import DEFAULT_VERSION_POLICY, VersionPolicy

if TYPE_CHECKING:
    from ..modules.album import AlbumApi
    from ..modules.comment import CommentApi
    from ..modules.login import LoginApi
    from ..modules.lyric import LyricApi
    from ..modules.mv import MvApi
    from ..modules.recommend import RecommendApi
    from ..modules.search import SearchApi
    from ..modules.singer import SingerApi
    from ..modules.song import SongApi
    from ..modules.songlist import SonglistApi
    from ..modules.top import TopApi
    from ..modules.user import UserApi
    from .request import Request, RequestGroup


R = TypeVar("R", bound=BaseModel | Struct | dict)


class RequestItem(TypedDict):
    """请求项"""

    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]


logger = logging.getLogger("qqmusicapi.client")


class ClientConfig(TypedDict, total=False):
    """Client 的可选底层网络配置"""

    proxy: Any
    trust_env: bool
    verify: Any
    cert: Any
    event_hooks: Any
    transport: Any
    mounts: Any


class _NullCookieJar(CookieJar):
    """绝对无状态的底层 Cookie 容器."""

    @override
    def set_cookie(self, cookie) -> None:
        """拦截并丢弃单一 Cookie 的写入动作."""
        pass

    @override
    def set_cookie_if_ok(self, cookie, request) -> None:
        """拦截并丢弃经过安全策略校验的单一 Cookie 写入动作."""
        pass

    @override
    def extract_cookies(self, response, request) -> None:
        """完全阻断从 HTTP 响应头中提取并批量存储 Set-Cookie 的行为."""
        pass


class Client:
    """QQMusic API Client.

    管理底层 HTTP 请求、全局设备信息、QIMEI 以及鉴权凭据,并提供对各个业务 API 模块的访问入口。
    支持自动携带签名字段、防并发积压限制及批量请求的打包调度。
    """

    def __init__(
        self,
        credential: Credential | None = None,
        device_path: str | anyio.Path | None = None,
        enable_sign: bool = False,
        platform: str = "android",
        max_concurrency: int = 10,
        max_connections: int = 20,
        qimei_timeout: float = 1.5,
        **client_config: Unpack[ClientConfig],
    ):
        """初始化 Client 实例。

        Args:
            credential: 用户鉴权凭证,若不提供则创建空凭证。
            device_path: 设备信息持久化路径,默认保存至内存。
            enable_sign: 是否开启全局请求参数签名。
            platform: 默认请求使用的平台标识,默认为 "android"。
            max_concurrency: 单个 Client 实例最大并发请求数。
            max_connections: HTTP 连接池大小。
            qimei_timeout: 内部获取 QIMEI 接口的超时时间。
            **client_config: 传递给 httpx.AsyncClient 的底层选项。
        """
        self.credential = credential or Credential()
        self._guid = uuid.uuid4().hex

        from ..utils.device import DeviceManager

        self.device_store = DeviceManager(device_path)

        self.enable_sign = enable_sign
        self.platform = platform
        self.qimei_timeout = qimei_timeout
        self._version_policy: VersionPolicy = DEFAULT_VERSION_POLICY
        self._guid = uuid.uuid4().hex

        self._limiter = anyio.CapacityLimiter(max_concurrency)

        self._session = httpx.AsyncClient(
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
            http2=True,
            cookies=_NullCookieJar(),
            proxy=client_config.get("proxy"),
            trust_env=client_config.get("trust_env", True),
            verify=client_config.get("verify", True),
            cert=client_config.get("cert"),
            event_hooks=client_config.get("event_hooks"),
            transport=client_config.get("transport"),
            mounts=client_config.get("mounts"),
        )

        self._qimei_lock = anyio.Lock()
        self._qimei_loaded = False
        self._qimei_cache: QimeiResult | None = None

        from .middlewares import CommContextMiddleware, RequestMiddleware, SignDecisionMiddleware

        self._middlewares: list[RequestMiddleware] = [
            CommContextMiddleware(),
            SignDecisionMiddleware(),
        ]

    @property
    def comment(self) -> "CommentApi":
        """评论模块。"""
        from ..modules.comment import CommentApi

        return CommentApi(self)

    @property
    def recommend(self) -> "RecommendApi":
        """推荐模块。"""
        from ..modules.recommend import RecommendApi

        return RecommendApi(self)

    @property
    def top(self) -> "TopApi":
        """排行榜模块。"""
        from ..modules.top import TopApi

        return TopApi(self)

    @property
    def album(self) -> "AlbumApi":
        """专辑模块。"""
        from ..modules.album import AlbumApi

        return AlbumApi(self)

    @property
    def mv(self) -> "MvApi":
        """MV 模块。"""
        from ..modules.mv import MvApi

        return MvApi(self)

    @property
    def login(self) -> "LoginApi":
        """登录模块。"""
        from ..modules.login import LoginApi

        return LoginApi(self)

    @property
    def search(self) -> "SearchApi":
        """搜索模块。"""
        from ..modules.search import SearchApi

        return SearchApi(self)

    @property
    def lyric(self) -> "LyricApi":
        """歌词模块。"""
        from ..modules.lyric import LyricApi

        return LyricApi(self)

    @property
    def singer(self) -> "SingerApi":
        """歌手模块。"""
        from ..modules.singer import SingerApi

        return SingerApi(self)

    @property
    def song(self) -> "SongApi":
        """歌曲模块。"""
        from ..modules.song import SongApi

        return SongApi(self)

    @property
    def songlist(self) -> "SonglistApi":
        """歌单模块。"""
        from ..modules.songlist import SonglistApi

        return SonglistApi(self)

    @property
    def user(self) -> "UserApi":
        """用户模块。"""
        from ..modules.user import UserApi

        return UserApi(self)

    async def fetch(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发送底层 HTTP 请求。

        该方法提供并发控制及网络异常转换。

        Args:
            method: HTTP 方法,如 "GET" 或 "POST"。
            url: 请求的 URL 地址。
            **kwargs: 传递给 httpx.AsyncClient.request 的附加参数。

        Returns:
            httpx.Response: HTTP 响应对象。

        Raises:
            NetworkError: 网络请求过程中发生异常。
        """
        logger.debug("HTTP 请求开始: %s %s", method, url)
        await self._limiter.acquire()
        try:
            resp = await self._session.request(method, url, **kwargs)
            logger.debug("HTTP 请求完成: %s %s -> %s", method, url, resp.status_code)
            return resp
        except httpx.RequestError as exc:
            logger.warning("HTTP 请求失败: %s %s, error=%s", method, url, exc)
            raise NetworkError(f"Network error: {exc}", original_exc=exc) from exc
        finally:
            self._limiter.release()

    async def sync_device_workspace(self) -> None:
        """同步设备暂存工作区 (UID Drift 处理).

        当 Client 的凭据被赋予真实 QQ 时 (例如从游离到登录),
        自动将属于本实例先前的临时指纹挂载或舍弃, 改为转移到实名用户专有指纹文件中。
        """
        await self.device_store.sync_workspace(getattr(self.credential, "musicid", None))

    async def _ensure_device(self) -> "Device":
        """获取与当前凭证关联的设备信息(状态防漂移)。

        Returns:
            Device: 当前活动的设备对象。
        """
        return await self.device_store.get_device(getattr(self.credential, "musicid", None))

    async def _get_qimei_cached(self) -> QimeiResult | None:
        """获取并缓存 QIMEI 信息。

        如果设备对象中已有缓存则直接返回,否则向服务器请求新的 QIMEI,
        并将其持久化到设备存储中。该方法保证并发请求时的安全性(Lock)。

        Returns:
            QimeiResult | None: 成功则返回 QIMEI 字典数据,失败则返回 None。
        """
        if self._qimei_loaded:
            return self._qimei_cache

        async with self._qimei_lock:
            if self._qimei_loaded:
                return self._qimei_cache

            device = await self._ensure_device()
            if device.qimei and device.qimei36:
                self._qimei_cache = QimeiResult(q16=device.qimei, q36=device.qimei36)
                self._qimei_loaded = True
                return self._qimei_cache

            try:
                qimei_app_version = self._version_policy.get_qimei_app_version(self.platform)
                qimei_sdk_version = self._version_policy.get_qimei_sdk_version(self.platform)

                self._qimei_cache = await get_qimei(
                    device=device,
                    version=qimei_app_version,
                    session=self._session,
                    request_timeout=self.qimei_timeout,
                    sdk_version=qimei_sdk_version,
                )
                self._qimei_loaded = True

                if self._qimei_cache:
                    await self.device_store.apply_qimei(
                        self._qimei_cache.get("q16") or "",
                        self._qimei_cache.get("q36") or "",
                        getattr(self.credential, "musicid", None),
                    )

            except Exception as exc:
                logger.warning("获取 QIMEI 失败: %s", exc)
                self._qimei_cache = None
            return self._qimei_cache

    async def _build_common_params(self, platform: str | None, credential: Credential) -> dict[str, Any]:
        """构建 QQ 音乐接口的通用 comm 字典参数。

        提取对应的设备、QIMEI 信息、用户 UID 等,依据当前客户端平台装配到 comm 字典中。

        Args:
            platform: 目标平台名称。
            credential: 用户凭证。

        Returns:
            dict[str, Any]: 组装好的 comm 参数字典。
        """
        target_platform = platform or self.platform
        qimei = await self._get_qimei_cached() if target_platform in {"android", "android_jce"} else None
        qimei_data: dict[str, str] | None = None
        if qimei is not None:
            qimei_data = {"q16": qimei["q16"], "q36": qimei["q36"]}
        return self._version_policy.build_comm(
            platform=target_platform,
            credential=credential,
            device=await self._ensure_device(),
            qimei=qimei_data,
            guid=self._guid,
        )

    def request_group(self, batch_size: int = 20, max_inflight_batches: int = 5) -> "RequestGroup":
        """创建并返回一个批量请求(RequestGroup)容器。

        适用于需合并多个相同协议(JSON 或 JCE)请求的场景。

        Args:
            batch_size: 单个批次的最大请求数量。
            max_inflight_batches: 允许同时发送的最多批次数量。

        Returns:
            RequestGroup: 批量请求对象。
        """
        from .request import RequestGroup

        return RequestGroup(self, batch_size=batch_size, max_inflight_batches=max_inflight_batches)

    async def execute(self, request: "Request[R]") -> R:
        """执行单个请求描述符并解析返回结果。

        调用中间件进行请求预处理,随后根据请求格式(JCE/JSON)分发调用底层发包方法,
        解析响应后自动组装成预期的 `response_model` 类型。

        Args:
            request: 请求描述符对象。

        Returns:
            R: 解析后对应的响应对象模型。

        Raises:
            ApiError: 接口返回状态码异常或缺少预期字段。
        """
        for mw in self._middlewares:
            request = await mw.process_request(request, self)

        data: RequestItem = {
            "module": request.module,
            "method": request.method,
            "param": request.param,
        }

        if request.is_jce:
            response = await self.request_jce(data=data, comm=request.comm, credential=request.credential)
            item = response.data.get("req_0")
            if item is None:
                raise ApiError("缺少响应字段: req_0", code=-1, data=response)
            if item.code != 0:
                code, subcode = extract_api_error_code(item)
                logger.warning(
                    "JCE 请求返回错误: module=%s method=%s code=%s subcode=%s",
                    request.module,
                    request.method,
                    code,
                    subcode,
                )
                raise build_api_error(
                    code=code,
                    subcode=subcode,
                    data=item.data,
                    context={"module": request.module, "method": request.method, "is_jce": True},
                )
            return self._build_result(item.data, request.response_model)

        response = await self.request_musicu(
            data=data,
            comm=request.comm,
            credential=request.credential,
            platform=request.platform,
        )
        item = response.data.get("req_0")
        if item is None:
            raise ApiError("缺少响应字段: req_0", code=-1, data=response)
        if item.code != 0:
            code, subcode = extract_api_error_code(item)
            logger.warning(
                "JSON 请求返回错误: module=%s method=%s code=%s subcode=%s",
                request.module,
                request.method,
                code,
                subcode,
            )
            raise build_api_error(
                code=code,
                subcode=subcode,
                data=item.data,
                context={"module": request.module, "method": request.method, "is_jce": False},
            )
        return self._build_result(item.data, request.response_model)

    @staticmethod
    def _build_result(raw: Any, response_model: type[R] | None) -> R:
        """构建响应对象。

        Args:
            raw: 原始响应数据。
            response_model: 期望的响应模型类型,支持 Pydantic BaseModel 或 Tarsio Struct。

        Returns:
            R: 构建好的响应模型实例,或原样返回(如果无需转换)。
        """
        if response_model is None:
            return raw
        if isinstance(response_model, type):
            if issubclass(response_model, BaseModel):
                return response_model.model_validate(raw)  # type: ignore[return-value]
            if issubclass(response_model, Struct):
                from tarsio import encode

                return response_model.decode(encode(raw))  # type: ignore[return-value]
        return raw

    async def close(self) -> None:
        """关闭底层会话。"""
        await self._session.aclose()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _get_user_agent(self, platform: str | None = None) -> str:
        """根据指定或默认平台生成请求所需的 User-Agent。

        Args:
            platform: 平台标识。若为 None,使用当前 Client 默认平台。

        Returns:
            str: 格式化好的 User-Agent 字符串。
        """
        target_platform = platform or self.platform
        return self._version_policy.get_user_agent(target_platform, await self._ensure_device())

    def _get_cookies(self, credential: Credential | None = None) -> dict[str, str]:
        """从鉴权凭证中提取请求需附带的 Cookies。

        转换并映射 uin、qm_keyst 等鉴权字段为标准字典形式。

        Args:
            credential: 提供凭证对象。若为 None 则使用 Client 当前实例的全局凭证。

        Returns:
            dict[str, str]: 包含 Cookie 键值对的字典。
        """
        auth: dict[str, str] = {}
        cred = credential or self.credential
        if cred.musicid:
            auth["uin"] = str(cred.musicid)
            auth["qqmusic_uin"] = str(cred.musicid)
        if cred.musickey:
            auth["qm_keyst"] = cred.musickey
            auth["qqmusic_key"] = cred.musickey
        return auth

    async def request(
        self,
        method: str,
        url: str,
        credential: Credential | None = None,
        platform: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送带有凭证和 User-Agent 的 HTTP 请求。

        自动装配指定的客户端平台 User-Agent 及对应凭证的 Cookies。

        Args:
            method: HTTP 方法,如 "GET" 或 "POST"。
            url: 请求的 URL 地址。
            credential: 覆盖默认凭证,可选。
            platform: 覆盖默认平台,可选。
            **kwargs: 传递给 httpx 的其他参数。

        Returns:
            httpx.Response: HTTP 响应对象。
        """
        auth_cookies = self._get_cookies(credential)
        if "cookies" in kwargs:
            auth_cookies.update(kwargs["cookies"])
        if auth_cookies:
            kwargs["cookies"] = auth_cookies

        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = await self._get_user_agent(platform)
        kwargs["headers"] = headers

        logger.debug("发送请求: %s %s", method, url)
        return await self.fetch(method, url, **kwargs)

    async def request_musicu(
        self,
        data: RequestItem | list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        url: str = "https://u.y.qq.com/cgi-bin/musicu.fcg",
        platform: str | None = None,
        http_params_extra: dict[str, str] | None = None,
        http_headers_extra: dict[str, str] | None = None,
    ) -> JsonResponse:
        """发送标准 QQ 音乐请求 (Musicu/JSON) 并解析响应。

        Args:
            data: 请求项,支持单个或批量。
            comm: 请求公共参数。
            credential: 请求凭证(该方法底层未直接使用凭证参数,供扩展)。
            url: 请求的网关 URL,默认为 musicu.fcg。
            platform: 请求发起的平台名称。
            http_params_extra: 额外的 URL 参数。
            http_headers_extra: 额外的 HTTP 头信息。

        Returns:
            JsonResponse: 解析后的 JSON 响应对象。

        Raises:
            HTTPError: HTTP 状态码不是 200。
            ApiError: JSON 解析错误或缺少关键字段。
        """
        requests = data if isinstance(data, list) else [data]
        logger.debug("构建 JSON 批量请求: count=%s platform=%s", len(requests), platform or self.platform)

        payload_obj = JsonRequest(
            comm=comm or {},
            data=[
                JsonRequestItem(
                    module=req["module"],
                    method=req["method"],
                    param=bool_to_int(req["param"]),
                )
                for req in requests
            ],
        )
        payload = payload_obj.model_dump(mode="plain")

        params = dict(http_params_extra) if http_params_extra else {}
        if params.pop("_internal_need_sign", None) == "1" or self.enable_sign:
            from ..algorithms.sign import sign_request

            if signature := sign_request(payload):
                params["sign"] = signature

        resp = await self.fetch("POST", url, json=payload, params=params, headers=http_headers_extra)

        if resp.status_code != 200:
            raise HTTPError(f"请求失败: {resp.text[:500]}", status_code=resp.status_code)

        try:
            payload_data = json.loads(resp.content)
            return JsonResponse.model_validate(payload_data)
        except Exception as exc:
            raise ApiError(f"JSON 解析失败: {exc!s}", code=-1, data=resp.text[:500], cause=exc) from exc

    async def request_jce(
        self,
        data: RequestItem | list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        url: str = "http://u.y.qq.com/cgi-bin/musicw.fcg",
        http_params_extra: dict[str, str] | None = None,
        http_headers_extra: dict[str, str] | None = None,
    ) -> JceResponse:
        """发送 JCE 格式的请求并解析响应。

        Args:
            data: JCE 请求项,支持单个或批量。
            comm: 请求公共参数。
            credential: 请求凭证。
            url: JCE 网关 URL。
            http_params_extra: 额外的 URL 参数。
            http_headers_extra: 额外的 HTTP 头信息。

        Returns:
            JceResponse: 解析后的 JCE 响应对象。

        Raises:
            HTTPError: HTTP 状态码不是 200。
            ApiError: JCE 解析失败。
        """
        requests = data if isinstance(data, list) else [data]
        logger.debug("构建 JCE 批量请求: count=%s", len(requests))

        def _ensure_jce_param(p: dict[str, Any] | dict[int, Any]) -> dict[int, Any]:
            if not isinstance(p, dict) or not all(isinstance(k, int) for k in p):
                raise TypeError("JCE param 必须是 dict[int, Any]")
            return cast(dict[int, Any], p)

        payload = JceRequest(
            comm or {},
            {
                f"req_{idx}": JceRequestItem(
                    module=req["module"],
                    method=req["method"],
                    param=TarsDict(_ensure_jce_param(req["param"])),
                )
                for idx, req in enumerate(requests)
            },
        ).encode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": await self._get_user_agent("android"),
            "x-sign-data-type": "jce",
        }
        if http_headers_extra:
            headers.update(http_headers_extra)

        resp = await self.fetch("POST", url, content=payload, headers=headers, params=http_params_extra)

        if resp.status_code != 200:
            raise HTTPError(f"请求失败: {resp.text[:500]}", status_code=resp.status_code)

        try:
            return JceResponse.decode(resp.content)
        except Exception as exc:
            data_preview = resp.text[:500] if isinstance(resp.text, str) else str(resp.content[:500])
            raise ApiError(f"JCE 响应解析失败: {exc!s}", code=-1, data=data_preview, cause=exc) from exc
