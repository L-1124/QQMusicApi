"""API 客户端核心实现. 整合网络传输、鉴权与业务模块访问."""

import uuid
from collections import defaultdict
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from niquests import AsyncSession, AsyncTokenBucketLimiter, PreparedRequest
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType
from tarsio import TarsDict
from urllib3.util.retry import Retry

from ..models.request import Credential, JceRequest, JceRequestItem, JceResponse, JceResponseItem, RequestItem
from ..utils.common import bool_to_int
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .exceptions import (
    ApiDataError,
    CgiApiException,
    CredentialExpiredError,
    GlobalApiError,
    HTTPError,
    RatelimitedError,
)
from .request import Request, RequestResultT, _build_result
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

_SENTINEL = object()


class Client:
    """QQMusic API Client."""

    def __init__(
        self,
        credential: Credential | None = None,
        *,
        platform: Platform | None = None,
        device_path: str | None = None,
        rate: float | None = None,
        capacity: float | None = None,
        connect_retries: int | None = None,
        proxies: ProxyType | None = None,
        cert: TLSClientCertType | None = None,
        hooks: AsyncHookType[PreparedRequest | Response] | None = None,
        verify: TLSVerifyType | None = None,
    ):
        """初始化客户端实例.

        Args:
            credential: 全局默认凭证.
            platform: 全局默认请求平台.
            device_path: 设备信息文件路径.
            rate: 请求速率限制 (请求/秒). 默认为 10.
            capacity: 令牌桶容量, 允许的突发请求数. 默认为 50.
            connect_retries: 连接建立失败时的最大重试次数. 默认为 2.
            proxies: 代理配置, 详见 niquests 文档.
            cert: TLS 客户端证书配置, 详见 niquests 文档.
            verify: TLS 证书验证配置, 详见 niquests 文档.
            hooks: 请求/响应钩子, 详见 niquests 文档.
        """
        self._session = AsyncSession(
            multiplexed=True,
            hooks=AsyncTokenBucketLimiter(rate=rate or 10, capacity=capacity or 50),
            happy_eyeballs=True,
            retries=Retry(
                total=connect_retries or 2,
                connect=connect_retries or 2,
                read=0,
                redirect=0,
                status=0,
                other=0,
                backoff_factor=0.2,
            ),
        )
        self.credential = credential or Credential()
        self.platform = platform or Platform.ANDROID

        self.proxies = proxies
        self.cert = cert
        self.verify = verify
        self.hooks = hooks

        self._device_store = DeviceManager(device_path)

        self._guid = uuid.uuid4().hex
        self._version_policy: VersionPolicy = DEFAULT_VERSION_POLICY
        self._qimei_manager = QimeiManager(
            device_store=self._device_store,
            app_version=self._version_policy.get_qimei_app_version(),
            sdk_version=self._version_policy.get_qimei_sdk_version(),
            session=self._session,
        )

    @cached_property
    def comment(self) -> "CommentApi":
        """评论模块."""
        from ..modules.comment import CommentApi

        return CommentApi(self)

    @cached_property
    def recommend(self) -> "RecommendApi":
        """推荐模块."""
        from ..modules.recommend import RecommendApi

        return RecommendApi(self)

    @cached_property
    def top(self) -> "TopApi":
        """排行榜模块."""
        from ..modules.top import TopApi

        return TopApi(self)

    @cached_property
    def album(self) -> "AlbumApi":
        """专辑模块."""
        from ..modules.album import AlbumApi

        return AlbumApi(self)

    @cached_property
    def mv(self) -> "MvApi":
        """MV 模块."""
        from ..modules.mv import MvApi

        return MvApi(self)

    @cached_property
    def login(self) -> "LoginApi":
        """登录模块."""
        from ..modules.login import LoginApi

        return LoginApi(self)

    @cached_property
    def search(self) -> "SearchApi":
        """搜索模块."""
        from ..modules.search import SearchApi

        return SearchApi(self)

    @cached_property
    def lyric(self) -> "LyricApi":
        """歌词模块."""
        from ..modules.lyric import LyricApi

        return LyricApi(self)

    @cached_property
    def singer(self) -> "SingerApi":
        """歌手模块."""
        from ..modules.singer import SingerApi

        return SingerApi(self)

    @cached_property
    def song(self) -> "SongApi":
        """歌曲模块."""
        from ..modules.song import SongApi

        return SongApi(self)

    @cached_property
    def songlist(self) -> "SonglistApi":
        """歌单模块."""
        from ..modules.songlist import SonglistApi

        return SonglistApi(self)

    @cached_property
    def user(self) -> "UserApi":
        """用户模块."""
        from ..modules.user import UserApi

        return UserApi(self)

    async def __aenter__(self) -> "Client":  # noqa: D105
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: D105
        await self.close()

    async def close(self):
        """关闭客户端连接."""
        await self._session.close()

    async def _get_user_agent(self, platform: Platform | None = None) -> str:
        """根据指定或默认平台生成请求所需的 User-Agent.

        Args:
            platform: 平台标识. 若为 None, 使用当前 Client 默认平台.

        Returns:
            格式化好的 User-Agent 字符串.
        """
        target_platform = platform or self.platform
        return self._version_policy.get_user_agent(target_platform, await self._device_store.get_device())

    async def request(
        self,
        method: str,
        url: str,
        credential: Credential | None = None,
        platform: Platform | None = None,
        *,
        lazy: bool = False,
        **kwargs: Any,
    ):
        """发送带有凭证和 User-Agent 的 HTTP 请求.

        自动装配指定的客户端平台 User-Agent 及对应凭证的 Cookies.

        Args:
            method: HTTP 方法.
            url: URL 地址.
            credential: 请求凭证.
            platform: 请求平台.
            lazy: 是否延迟发送请求.
            **kwargs: 其他参数.
        """
        cred = credential or self.credential
        user_cookies = kwargs.pop("cookies", {})
        cookies: dict[str, str] = {}
        if cred.musicid:
            cookies["uin"] = cred.str_musicid or str(cred.musicid)
            cookies["qqmusic_uin"] = cred.str_musicid or str(cred.musicid)
        if cred.musickey:
            cookies["qm_keyst"] = cred.musickey
            cookies["qqmusic_key"] = cred.musickey
        cookies.update(user_cookies)
        if cookies:
            kwargs["cookies"] = cookies

        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = await self._get_user_agent(platform)
        kwargs["headers"] = headers

        resp = await self._session.request(
            method,
            url,
            **kwargs,
            proxies=self.proxies,
            hooks=self.hooks,
            cert=self.cert,
            verify=self.verify,
        )
        if not lazy:
            await self._session.gather(resp)
        return resp

    async def request_api(
        self,
        data: list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        *,
        is_jce: bool = False,
        lazy: bool = False,
    ) -> Response:
        """发送 API 请求."""
        platform = Platform.ANDROID if is_jce else platform or self.platform
        finalcomm = self._version_policy.build_comm(
            platform=platform,
            credential=credential or self.credential,
            device=await self._device_store.get_device(),
            qimei=cast("dict[str, str]", await self._qimei_manager.get_cached())
            if platform == Platform.ANDROID
            else None,
            guid=self._guid,
        )
        if comm:
            finalcomm.update(comm)

        user_agent = await self._get_user_agent(platform)

        if is_jce:
            for k, v in finalcomm.items():
                if not isinstance(v, str):
                    finalcomm[k] = str(v)
            content = JceRequest(
                finalcomm,
                {
                    f"req_{idx}": JceRequestItem(
                        module=req["module"],
                        method=req["method"],
                        param=TarsDict(cast("dict[int, Any]", req["param"])),
                    )
                    for idx, req in enumerate(data)
                },
            ).encode()
            resp = await self._session.post(
                "http://u.y.qq.com/cgi-bin/musicw.fcg",
                data=content,
                headers={"User-Agent": user_agent},
                proxies=self.proxies,
                hooks=self.hooks,
                cert=self.cert,
                verify=self.verify,
            )
            if not lazy:
                await self._session.gather(resp)
            return resp

        payload: dict[str, Any] = {
            "comm": finalcomm,
        }
        params = {}
        for idx, req in enumerate(data):
            payload[f"req_{idx}"] = {
                "module": req["module"],
                "method": req["method"],
                "param": req["param"] if req["preserve_bool"] else bool_to_int(req["param"]),
            }

        resp = await self._session.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            json=payload,
            params=params,
            headers={"User-Agent": user_agent},
            proxies=self.proxies,
            hooks=self.hooks,
            cert=self.cert,
            verify=self.verify,
        )
        if not lazy:
            await self._session.gather(resp)

        return resp

    @overload
    async def gather(
        self,
        requests: list[Request[RequestResultT]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[False] = False,
    ) -> list[RequestResultT]: ...

    @overload
    async def gather(
        self,
        requests: list[Request[RequestResultT]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[True],
    ) -> list[RequestResultT | Exception]: ...

    @overload
    async def gather(
        self,
        requests: list[Request[Any]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[False] = False,
    ) -> list[Any]: ...

    @overload
    async def gather(
        self,
        requests: list[Request[Any]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[True],
    ) -> list[Any | Exception]: ...

    async def gather(
        self,
        requests: list[Request[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求描述符并按输入顺序返回解析结果.

        可合并的请求会按协议、平台、公共参数和凭证分组, 每组按
        `batch_size` 拆分为批量请求发送。响应解析失败时, 默认抛出
        第一个异常; 当 `return_exceptions` 为 True 时, 异常会作为对应
        位置的结果返回。

        Args:
            requests: 待执行的请求描述符列表.
            batch_size: 每个批量请求包含的最大请求数.
            return_exceptions: 是否将单项解析异常作为结果返回.

        Returns:
            与 `requests` 顺序一致的解析结果列表.

        Raises:
            ValueError: 当 `batch_size` 小于等于 0, 响应为空, 响应缺少对应
                请求项, 或结果未能完整回填时抛出.
        """
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")

        if not requests:
            return []

        grouped_indices: dict[Any, list[int]] = defaultdict(list)
        for index, request in enumerate(requests):
            grouped_indices[request._group_key].append(index)

        batch_responses: list[tuple[list[int], Response]] = []

        for indices in grouped_indices.values():
            base_req = requests[indices[0]]

            for start in range(0, len(indices), batch_size):
                batch_indices = indices[start : start + batch_size]
                response_task = await self.request_api(
                    data=[
                        {
                            "module": requests[i].module,
                            "method": requests[i].method,
                            "param": requests[i].param,
                            "preserve_bool": requests[i].preserve_bool,
                        }
                        for i in batch_indices
                    ],
                    comm=base_req.comm,
                    credential=base_req.credential,
                    platform=base_req.platform,
                    is_jce=base_req.is_jce,
                    lazy=True,
                )
                batch_responses.append((batch_indices, response_task))

        await self._session.gather(*(resp for _, resp in batch_responses))

        results: list[Any] = [_SENTINEL] * len(requests)

        for batch_indices, response in batch_responses:
            data = self._vaildate_resp(response, is_jce=requests[batch_indices[0]].is_jce)
            for batch_index, req_index in enumerate(batch_indices):
                request = requests[req_index]
                try:
                    results[req_index] = self._parse_cgi_item(
                        data[f"req_{batch_index}"],
                        request,
                    )
                except Exception as exc:
                    if return_exceptions:
                        results[req_index] = exc
                    else:
                        raise

        missing_indexes = [i for i, res in enumerate(results) if res is _SENTINEL]
        if missing_indexes:
            raise ApiDataError(f"缺少以下索引结果: {missing_indexes}")

        return results

    def _vaildate_resp(self, response: Response, *, is_jce: bool) -> dict[str, Any]:
        """验证响应的基本有效性."""
        if response.status_code != 200:
            raise HTTPError(
                f"HTTP 请求状态码异常: {response.status_code}",
                status_code=cast("int", response.status_code),
            )
        if not response.content:
            raise ApiDataError("响应无内容")
        try:
            resp = JceResponse.decode(response.content) if is_jce else response.json()
        except Exception as exc:
            raise ApiDataError("响应内容非有效 JCE 格式") from exc
        code: int = resp.code if is_jce else cast("dict", resp).pop("code", 0)

        if code != 0:
            raise GlobalApiError("Module 请求失败", code=code, data=response.text)

        return resp.data if is_jce else cast("Any", resp)

    def _parse_cgi_item(
        self,
        item: dict[str, Any] | JceResponseItem,
        request: Request[RequestResultT],
    ) -> RequestResultT:
        """解析单个 CGI 响应项."""
        if isinstance(item, JceResponseItem):
            code = item.code
            data = item.data
        else:
            code: int = item.get("code", 0)
            data = item.get("data", {})

        if request.allow_error_codes and (
            code == 0 or (request.allow_error_codes == "all" or code in request.allow_error_codes)
        ):
            return cast(
                "RequestResultT",
                {"code": code, "data": data} if request.is_jce else item,
            )

        match code:
            case 2001:
                raise RatelimitedError(code=code, data=data)
            case 1000 | 104401 | 104400:
                raise CredentialExpiredError(code=code, data=data)
            case int() if code != 0:
                raise CgiApiException(code=code, data=data)

        return cast("RequestResultT", _build_result(data, request.response_model))

    async def execute(self, request: Request[RequestResultT]) -> RequestResultT:
        """执行单个请求描述符并解析响应结果.

        Args:
            request: 待执行的请求描述符.

        Returns:
            解析后的响应数据或响应模型.

        Raises:
            ValueError: 当响应为空、业务返回码非 0 或响应缺少 `req_0` 时抛出.
        """
        resp = await self.request_api(
            data=[
                {
                    "module": request.module,
                    "method": request.method,
                    "param": request.param,
                    "preserve_bool": request.preserve_bool,
                }
            ],
            comm=request.comm,
            credential=request.credential,
            platform=request.platform,
            is_jce=request.is_jce,
        )
        return self._parse_cgi_item(self._vaildate_resp(resp, is_jce=request.is_jce)["req_0"], request)
