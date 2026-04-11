"""API 客户端核心实现. 整合网络传输、鉴权与业务模块访问."""

import logging
import sys
import uuid
from collections.abc import Callable, Mapping
from http.cookiejar import CookieJar
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar, cast, overload

from httpx_retries import Retry, RetryTransport
from typing_extensions import override

if sys.version_info >= (3, 11):
    from typing import Unpack
else:
    from typing_extensions import Unpack

import anyio
import httpx
import orjson as json
from pydantic import BaseModel
from tarsio import TarsDict

from ..models.request import (
    Credential,
    JceRequest,
    JceRequestItem,
    JceResponse,
    RequestItem,
)
from ..utils.common import bool_to_int
from ..utils.qimei import QimeiResult, get_qimei
from .exceptions import ApiDataError, ApiError, HTTPError, NetworkError, _build_api_error, _extract_api_error_code
from .request import Request, RequestGroup, RequestResult, RequestResultT, ResponseModel
from .versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy

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
    from ..utils.device import Device


logger = logging.getLogger("qqmusicapi.client")
ModuleT = TypeVar("ModuleT")
_HTTP_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.WriteError,
    httpx.WriteTimeout,
)
_HTTP_RETRYABLE_METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")


class ClientConfig(TypedDict, total=False):
    """支持透传的 `httpx.AsyncClient` 的配置项."""

    proxy: Any
    """代理配置, 详见 `httpx.AsyncClient` 的 `proxy` 参数."""
    trust_env: bool
    """是否信任环境变量中的代理设置, 详见 `httpx.AsyncClient` 的 `trust_env` 参数."""
    verify: Any
    """SSL 证书验证配置, 详见 `httpx.AsyncClient` 的 `verify` 参数."""
    cert: Any
    """客户端证书配置, 详见 `httpx.AsyncClient` 的 `cert` 参数."""
    event_hooks: Any
    """事件钩子配置, 详见 `httpx.AsyncClient` 的 `event_hooks` 参数."""
    transport: Any
    """自定义传输后端, 详见 `httpx.AsyncClient` 的 `transport` 参数."""
    mounts: Any
    """自定义协议适配器, 详见 `httpx.AsyncClient` 的 `mounts` 参数."""


class _NullCookieJar(CookieJar):
    """无状态的底层 Cookie 容器."""

    @override
    def set_cookie(self, cookie) -> None:
        """拦截并丢弃单一 Cookie 的写入动作."""

    @override
    def set_cookie_if_ok(self, cookie, request) -> None:
        """拦截并丢弃经过安全策略校验的单一 Cookie 写入动作."""

    @override
    def extract_cookies(self, response, request) -> None:
        """完全阻断从 HTTP 响应头中提取并批量存储 Set-Cookie 的行为."""


class Client:
    """QQMusic API Client.

    管理底层 HTTP 请求、全局设备信息、QIMEI 以及鉴权凭证, 并提供对各个业务 API 模块的访问入口.
    模块属性会在同一个 Client 实例内懒加载并复用, 以共享对应的模块状态.
    支持自动携带签名字段、防并发积压限制及批量请求的打包调度.
    """

    def __init__(
        self,
        credential: Credential | None = None,
        device_path: str | anyio.Path | None = None,
        *,
        enable_sign: bool = False,
        platform: Platform = Platform.ANDROID,
        max_concurrency: int = 10,
        max_connections: int = 20,
        qimei_timeout: float = 1.5,
        **client_config: Unpack[ClientConfig],
    ):
        """初始化 Client 实例.

        Args:
            credential: 用户鉴权凭证, 若不提供则创建空凭证.
            device_path: 单个设备信息文件路径. 若为 None, 则为当前 Client 在内存生成新设备;
                若路径存在, 则从文件加载并复用; 若路径不存在, 则生成新设备并立即保存.
            enable_sign: 是否开启全局请求参数签名.
            platform: 默认请求使用的平台标识, 默认为 "android".
            max_concurrency: 单个 Client 实例最大并发请求数.
            max_connections: HTTP 连接池大小.
            qimei_timeout: 内部获取 QIMEI 接口的超时时间.
            **client_config: 传递给 httpx.AsyncClient 的底层选项.
        """
        self.credential = credential or Credential()
        self._guid = uuid.uuid4().hex

        from ..utils.device import DeviceManager

        self.device_store = DeviceManager(device_path)

        self.enable_sign = enable_sign
        self.platform = platform
        self._qimei_timeout = qimei_timeout
        self._version_policy: VersionPolicy = DEFAULT_VERSION_POLICY

        self._limiter = anyio.CapacityLimiter(max_concurrency)
        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_connections,
        )
        retry_policy = Retry(
            total=2,
            allowed_methods=_HTTP_RETRYABLE_METHODS,
            status_forcelist=[],
            retry_on_exceptions=_HTTP_RETRYABLE_EXCEPTIONS,
            backoff_factor=0.5,
            backoff_jitter=0.0,
        )
        transport = self._build_retry_transport(
            retry_policy,
            transport=client_config.get("transport"),
            proxy=client_config.get("proxy"),
            trust_env=client_config.get("trust_env", True),
            verify=client_config.get("verify", True),
            cert=client_config.get("cert"),
            limits=limits,
            http2=True,
        )
        mounts = self._wrap_mount_transports(client_config.get("mounts"), retry_policy)

        self._session = httpx.AsyncClient(
            follow_redirects=False,
            cookies=_NullCookieJar(),
            timeout=httpx.Timeout(5.0, read=10.0, write=5.0, pool=10.0),
            event_hooks=client_config.get("event_hooks"),
            transport=transport,
            mounts=mounts,
        )

        self._qimei_lock = anyio.Lock()
        self._qimei_loaded = False
        self._qimei_cache: QimeiResult | None = None
        self._module_cache: dict[str, Any] = {}

    @staticmethod
    def _build_retry_transport(
        retry_policy: Retry,
        *,
        transport: httpx.AsyncBaseTransport | None,
        proxy: Any,
        trust_env: bool,
        verify: Any,
        cert: Any,
        limits: httpx.Limits,
        http2: bool,
    ) -> RetryTransport:
        """构造带重试能力的底层 transport."""
        if transport is not None and not isinstance(transport, httpx.AsyncBaseTransport):
            raise TypeError("client_config.transport must be an httpx.AsyncBaseTransport")
        if transport is None:
            transport = httpx.AsyncHTTPTransport(
                verify=verify,
                cert=cert,
                trust_env=trust_env,
                http2=http2,
                limits=limits,
                proxy=proxy,
            )
        return RetryTransport(transport=transport, retry=retry_policy)

    @staticmethod
    def _wrap_mount_transports(
        mounts: Mapping[str, httpx.AsyncBaseTransport | None] | None,
        retry_policy: Retry,
    ) -> Mapping[str, httpx.AsyncBaseTransport | None] | None:
        """为 mounted transport 补上与默认请求一致的重试策略."""
        if mounts is None:
            return None

        wrapped_mounts: dict[str, httpx.AsyncBaseTransport | None] = {}
        for key, transport in mounts.items():
            if transport is not None and not isinstance(transport, httpx.AsyncBaseTransport):
                raise TypeError(f"client_config.mounts[{key!r}] must be an httpx.AsyncBaseTransport")
            wrapped_mounts[key] = None if transport is None else RetryTransport(transport=transport, retry=retry_policy)
        return wrapped_mounts

    def _get_module(self, name: str, factory: Callable[[], ModuleT]) -> ModuleT:
        """获取并缓存模块实例."""
        module = self._module_cache.get(name)
        if module is None:
            module = factory()
            self._module_cache[name] = module
        return cast("ModuleT", module)

    @property
    def comment(self) -> "CommentApi":
        """评论模块."""
        from ..modules.comment import CommentApi

        return self._get_module("comment", lambda: CommentApi(self))

    @property
    def recommend(self) -> "RecommendApi":
        """推荐模块."""
        from ..modules.recommend import RecommendApi

        return self._get_module("recommend", lambda: RecommendApi(self))

    @property
    def top(self) -> "TopApi":
        """排行榜模块."""
        from ..modules.top import TopApi

        return self._get_module("top", lambda: TopApi(self))

    @property
    def album(self) -> "AlbumApi":
        """专辑模块."""
        from ..modules.album import AlbumApi

        return self._get_module("album", lambda: AlbumApi(self))

    @property
    def mv(self) -> "MvApi":
        """MV 模块."""
        from ..modules.mv import MvApi

        return self._get_module("mv", lambda: MvApi(self))

    @property
    def login(self) -> "LoginApi":
        """登录模块."""
        from ..modules.login import LoginApi

        return self._get_module("login", lambda: LoginApi(self))

    @property
    def search(self) -> "SearchApi":
        """搜索模块."""
        from ..modules.search import SearchApi

        return self._get_module("search", lambda: SearchApi(self))

    @property
    def lyric(self) -> "LyricApi":
        """歌词模块."""
        from ..modules.lyric import LyricApi

        return self._get_module("lyric", lambda: LyricApi(self))

    @property
    def singer(self) -> "SingerApi":
        """歌手模块."""
        from ..modules.singer import SingerApi

        return self._get_module("singer", lambda: SingerApi(self))

    @property
    def song(self) -> "SongApi":
        """歌曲模块."""
        from ..modules.song import SongApi

        return self._get_module("song", lambda: SongApi(self))

    @property
    def songlist(self) -> "SonglistApi":
        """歌单模块."""
        from ..modules.songlist import SonglistApi

        return self._get_module("songlist", lambda: SonglistApi(self))

    @property
    def user(self) -> "UserApi":
        """用户模块."""
        from ..modules.user import UserApi

        return self._get_module("user", lambda: UserApi(self))

    async def fetch(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发送底层 HTTP 请求.

        该方法提供并发控制、网络波动自动重试及网络异常转换.

        Args:
            method: HTTP 方法, 如 "GET" 或 "POST".
            url: 请求的 URL 地址.
            **kwargs: 传递给 httpx.AsyncClient.request 的附加参数.

        Returns:
            HTTP 响应对象.

        Raises:
            NetworkError: 网络请求在重试耗尽后仍然失败.
        """
        logger.debug("HTTP 请求开始: %s %s", method, url)

        await self._limiter.acquire()
        try:
            resp = await self._session.request(method, url, **kwargs)
            logger.debug("HTTP 请求完成: %s %s -> %s", method, url, resp.status_code)
            return resp
        except httpx.RequestError as exc:
            logger.debug("HTTP 请求重试耗尽: %s %s, error=%s", method, url, exc)
            raise NetworkError(f"Network error: {exc}", original_exc=exc) from exc
        finally:
            self._limiter.release()

    async def _ensure_device(self) -> "Device":
        """获取与当前 Client 绑定的设备信息.

        Returns:
            Device: 当前活动的设备对象.
        """
        return await self.device_store.get_device()

    async def _get_qimei_cached(self) -> QimeiResult | None:
        """获取并缓存 QIMEI 信息.

        如果设备对象中已有缓存则直接返回, 否则向服务器请求新的 QIMEI,
        并将其持久化到当前 Client 绑定的设备存储中. 该方法保证并发请求时的安全性 (Lock).

        Returns:
            成功则返回 QIMEI 字典数据, 失败则返回 None.
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
                self._qimei_cache = await get_qimei(
                    device=device,
                    version=self._version_policy.get_qimei_app_version(),
                    session=self._session,
                    request_timeout=self._qimei_timeout,
                    sdk_version=self._version_policy.get_qimei_sdk_version(),
                )
                self._qimei_loaded = True

                if self._qimei_cache:
                    await self.device_store.apply_qimei(
                        self._qimei_cache.get("q16") or "",
                        self._qimei_cache.get("q36") or "",
                    )

            except Exception as exc:
                logger.debug("获取 QIMEI 失败: %s", exc)
                self._qimei_cache = None
            return self._qimei_cache

    async def _build_common_params(
        self,
        platform: Platform | None,
        credential: Credential,
        comm: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建 QQ 音乐接口的通用 comm 字典参数.

        提取对应的设备、QIMEI 信息、用户 UID 等, 依据当前客户端平台装配到 comm 字典中.

        Args:
            platform: 目标平台名称.
            credential: 用户凭证.
            comm: 额外覆盖或补充的 comm 字段, 将覆盖默认生成的字段.

        Returns:
            组装好的 comm 参数字典.
        """
        target_platform = platform or self.platform
        qimei = await self._get_qimei_cached() if target_platform == Platform.ANDROID else None
        basecomm = self._version_policy.build_comm(
            platform=target_platform,
            credential=credential,
            device=await self._ensure_device(),
            qimei={"q16": qimei["q16"], "q36": qimei["q36"]} if qimei is not None else None,
            guid=self._guid,
        )
        if comm:
            basecomm.update(comm)
        return basecomm

    def request_group(self, batch_size: int = 20, max_inflight_batches: int = 5) -> "RequestGroup":
        """创建并返回一个批量请求 (RequestGroup) 容器.

        适用于需合并多个相同协议 (JSON 或 JCE) 请求的场景.

        Args:
            batch_size: 单个批次的最大请求数量.
            max_inflight_batches: 允许同时发送的最多批次数量.

        Returns:
            批量请求对象.
        """
        from .request import RequestGroup

        return RequestGroup(self, batch_size=batch_size, max_inflight_batches=max_inflight_batches)

    @overload
    async def execute(self, request: "Request[RequestResultT]") -> "RequestResultT": ...

    @overload
    async def execute(self, request: "Request") -> dict[str, Any] | dict[int, Any]: ...

    async def execute(self, request: "Request") -> Any:
        """执行单个请求描述符并解析返回结果.

        调用中间件进行请求预处理, 随后根据请求格式 (JCE/JSON) 分发调用底层发包方法,
        解析响应后自动组装成预期的 `response_model` 类型.

        Args:
            request: 请求描述符对象.

        Returns:
            解析后对应的响应对象模型.

        Raises:
            ApiError: 接口返回状态码异常或缺少预期字段.
        """
        data: RequestItem = {
            "module": request.module,
            "method": request.method,
            "param": request.param,
        }
        if request.is_jce:
            response = await self.request_jce(
                data=data,
                comm=request.comm,
                credential=request.credential,
            )
            item = response.data.get("req_0")
            if item is None:
                raise ApiError("缺少响应字段: req_0", code=-1, data=response)
            if item.code != 0:
                code, subcode = _extract_api_error_code(item)
                logger.debug(
                    "JCE 请求返回错误: module=%s method=%s code=%s subcode=%s",
                    request.module,
                    request.method,
                    code,
                    subcode,
                )
                raise _build_api_error(
                    code=code,
                    subcode=subcode,
                    data=item.data,
                    context={"module": request.module, "method": request.method, "is_jce": True},
                )
            if item.data is None:
                raise ApiError("缺少响应数据: req_0.data", code=-1, data=item)
            if request.response_model is None:
                return item.data
            try:
                return self._build_result(item.data, request.response_model)
            except Exception as exc:
                raise ApiError("响应数据校验失败", code=-1, data=item.data, cause=exc) from exc

        response = await self.request_musicu(
            data=data,
            comm=request.comm,
            platform=request.platform,
            credential=request.credential,
            preserve_bool=request.preserve_bool,
        )
        item = response.get("req_0")
        if item is None:
            raise ApiError("缺少响应字段: req_0", code=-1, data=response)
        code, subcode = _extract_api_error_code(item)
        if code is not None and code != 0:
            logger.debug(
                "JSON 请求返回错误: module=%s method=%s code=%s subcode=%s",
                request.module,
                request.method,
                code,
                subcode,
            )
            raise _build_api_error(
                code=code,
                subcode=subcode,
                data=item.get("data"),
                context={"module": request.module, "method": request.method, "is_jce": False},
            )
        response_model = request.response_model
        raw = item.get("data", {})
        if not raw:
            raise ApiDataError("缺少响应数据: req_0.data", data=item)

        # dump_path = anyio.Path(f"responses/{request.module}_{request.method}.json")
        # await dump_path.parent.mkdir(parents=True, exist_ok=True)
        # await dump_path.write_text(json.dumps(raw).decode("utf-8"))
        if response_model is None:
            return raw
        try:
            return self._build_result(raw, response_model)
        except Exception as exc:
            raise ApiDataError("响应数据校验失败", data=raw) from exc

    @overload
    @staticmethod
    def _build_result(
        raw: TarsDict | dict[str, Any],
        response_model: type["ResponseModel"],
    ) -> "ResponseModel": ...

    @overload
    @staticmethod
    def _build_result(
        raw: dict[str, Any],
        response_model: None,
    ) -> dict[str, Any]: ...

    @overload
    @staticmethod
    def _build_result(
        raw: TarsDict,
        response_model: None,
    ) -> TarsDict: ...

    @staticmethod
    def _build_result(
        raw: TarsDict | dict[str, Any],
        response_model: type[BaseModel] | None,
    ) -> RequestResult:
        """构建响应对象.

        Args:
            raw: 原始响应数据.
            response_model: 期望的响应模型类型, 支持 Pydantic BaseModel.

        Returns:
            构建好的响应模型实例, 或原样返回 (如果无需转换).
        """
        if response_model is None:
            return raw
        if issubclass(response_model, BaseModel):
            return response_model.model_validate(raw)
        return raw

    async def close(self) -> None:
        """关闭底层会话."""
        await self._session.aclose()

    async def __aenter__(self) -> "Client":
        """获取 Client 实例."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """自动关闭 Client.

        Args:
            exc_type: 异常类型.
            exc_val: 异常值.
            exc_tb: 异常回溯.
        """
        await self.close()

    async def _get_user_agent(self, platform: Platform | None = None) -> str:
        """根据指定或默认平台生成请求所需的 User-Agent.

        Args:
            platform: 平台标识. 若为 None, 使用当前 Client 默认平台.

        Returns:
            格式化好的 User-Agent 字符串.
        """
        target_platform = platform or self.platform
        return self._version_policy.get_user_agent(target_platform, await self._ensure_device())

    def _get_cookies(self, credential: Credential | None = None) -> dict[str, str]:
        """从鉴权凭证中提取请求需附带的 Cookies.

        转换并映射 uin、qm_keyst 等鉴权字段为标准字典形式.

        Args:
            credential: 提供凭证对象. 若为 None 则使用 Client 当前实例的全局凭证.

        Returns:
            包含 Cookie 键值对的字典.
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
        platform: Platform | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送带有凭证和 User-Agent 的 HTTP 请求.

        自动装配指定的客户端平台 User-Agent 及对应凭证的 Cookies.

        Args:
            method: HTTP 方法, 如 "GET" 或 "POST".
            url: 请求的 URL 地址.
            credential: 覆盖默认凭证, 可选.
            platform: 覆盖默认平台, 可选.
            **kwargs: 传递给 httpx 的其他参数.

        Returns:
            HTTP 响应对象.
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
        platform: Platform | None = None,
        *,
        preserve_bool: bool = False,
    ) -> dict[str, Any]:
        """发送标准 QQ 音乐请求 (Musicu/JSON) 并解析响应.

        Args:
            data: 请求项, 支持单个或批量.
            comm: 请求公共参数.
            credential: 请求凭证 (该方法底层未直接使用凭证参数, 供扩展).
            url: 请求的网关 URL, 默认为 musicu.fcg.
            platform: 请求发起的平台名称.
            preserve_bool: 是否保留 JSON 参数中的布尔字面量.

        Returns:
            解析后的 JSON 响应字典.

        Raises:
            HTTPError: HTTP 状态码不是 200.
            ApiError: JSON 解析错误或缺少关键字段.
        """
        requests = data if isinstance(data, list) else [data]
        logger.debug(
            "构建 JSON 批量请求: count=%s platform=%s preserve_bool=%s",
            len(requests),
            platform or self.platform,
            preserve_bool,
        )

        payload: dict[str, Any] = {
            "comm": await self._build_common_params(platform, credential or self.credential, comm),
        }
        for idx, req in enumerate(requests):
            payload[f"req_{idx}"] = {
                "module": req["module"],
                "method": req["method"],
                "param": req["param"] if preserve_bool else bool_to_int(req["param"]),
            }

        params: dict[str, Any] = {}

        if self.enable_sign:
            from ..algorithms.sign import sign_request

            if signature := sign_request(payload):
                params["sign"] = signature

        resp = await self.fetch(
            "POST",
            url,
            json=payload,
            params=params,
            headers={
                "Content-Type": "application/json",
                "User-Agent": await self._get_user_agent(Platform.ANDROID),
            },
        )

        if resp.status_code != 200:
            raise HTTPError(f"请求失败: {resp.text[:500]}", status_code=resp.status_code)

        try:
            return json.loads(resp.content)
        except Exception as exc:
            raise ApiError(f"JSON 解析失败: {exc!s}", code=-1, data=resp.text[:500], cause=exc) from exc

    async def request_jce(
        self,
        data: RequestItem | list[RequestItem],
        credential: Credential | None = None,
        comm: dict[str, Any] | None = None,
        url: str = "http://u.y.qq.com/cgi-bin/musicw.fcg",
    ) -> JceResponse:
        """发送 Android 语义的 JCE 格式请求并解析响应.

        Args:
            data: JCE 请求项, 支持单个或批量.
            comm: 请求公共参数.
            credential: 请求凭证.
            url: JCE 网关 URL.

        Returns:
            解析后的 JCE 响应对象.

        Raises:
            HTTPError: HTTP 状态码不是 200.
            ApiError: JCE 解析失败.
        """
        requests = data if isinstance(data, list) else [data]
        logger.debug("构建 JCE 批量请求: count=%s", len(requests))

        def _ensure_jce_param(p: dict[str, Any] | dict[int, Any]) -> dict[int, Any]:
            if not all(isinstance(k, int) for k in p):
                raise TypeError("JCE param 必须是 dict[int, Any]")
            return {key: value for key, value in p.items() if isinstance(key, int)}

        payload = JceRequest(
            {
                k: str(v)
                for k, v in (
                    await self._build_common_params(Platform.ANDROID, credential or self.credential, comm)
                ).items()
            },
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
            "User-Agent": await self._get_user_agent(Platform.ANDROID),
            "x-sign-data-type": "jce",
        }

        resp = await self.fetch("POST", url, content=payload, headers=headers)

        if resp.status_code != 200:
            raise HTTPError(f"请求失败: {resp.text[:500]}", status_code=resp.status_code)

        try:
            return JceResponse.decode(resp.content)
        except Exception as exc:
            data_preview = resp.text[:500] if isinstance(resp.text, str) else str(resp.content[:500])
            raise ApiError(f"JCE 响应解析失败: {exc!s}", code=-1, data=data_preview, cause=exc) from exc
