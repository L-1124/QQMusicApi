"""API 客户端核心实现. 整合网络传输、鉴权与业务模块访问."""

import uuid
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from niquests import AsyncSession
from niquests.models import Response
from tarsio import TarsDict

from ..models.request import Credential, JceRequest, JceRequestItem, JceResponse, RequestItem
from ..utils.common import bool_to_int
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .exceptions import _build_api_error, _extract_api_error_code
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


class Client:
    """QQMusic API Client."""

    def __init__(
        self,
        credential: Credential | None = None,
        *,
        platform: Platform | None = None,
        device_path: str | None = None,
        enable_sign: bool = False,
    ):
        """初始化客户端实例."""
        self._session = AsyncSession()
        self.credential = credential or Credential()
        self.platform = platform or Platform.ANDROID
        self.enable_sign = enable_sign

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
        **kwargs: Any,
    ):
        """发送带有凭证和 User-Agent 的 HTTP 请求.

        自动装配指定的客户端平台 User-Agent 及对应凭证的 Cookies.

        Args:
            method: HTTP 方法.
            url: URL 地址.
            credential: 请求凭证.
            platform: 请求平台.
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

        return await self._session.request(
            method,
            url,
            **kwargs,
        )

    async def request_api(
        self,
        data: list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
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
            return await self._session.post(
                "http://u.y.qq.com/cgi-bin/musicw.fcg",
                data=content,
                headers={"User-Agent": user_agent},
            )

        payload: dict[str, Any] = {
            "comm": finalcomm,
        }
        for idx, req in enumerate(data):
            payload[f"req_{idx}"] = {
                "module": req["module"],
                "method": req["method"],
                "param": req["param"] if preserve_bool else bool_to_int(req["param"]),
            }
        params = {}

        return await self._session.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            json=payload,
            params=params,
            headers={"User-Agent": user_agent},
        )

    async def execute(self, request: Request[RequestResultT]) -> RequestResultT:
        """执行单个请求描述符并解析响应结果."""
        resp = await self.request_api(
            data=[
                {
                    "module": request.module,
                    "method": request.method,
                    "param": request.param,
                }
            ],
            comm=request.comm,
            credential=request.credential,
            platform=request.platform,
            is_jce=request.is_jce,
            preserve_bool=request.preserve_bool,
        )
        resp.raise_for_status()

        if not resp.content:
            raise ValueError("Empty response content")

        if request.is_jce:
            body = JceResponse.decode(resp.content)
            code = body.code
            req = body.data.get("data", None)
            if req is None:
                raise ValueError("Missing 'data' in JCE response")
            data = req.data
        else:
            body = resp.json()
            code = body.get("code", 0)
            req = body.get("req_0")
            if req is None:
                raise ValueError("Missing 'data' in JCE response")
            data = req.get("data", {})

        if code != 0:
            raise ValueError(f"API error with code {code}: {body}")

        req_code, subcode = _extract_api_error_code(req)
        if req_code != 0:
            raise _build_api_error(code=req_code, subcode=subcode)

        return cast("RequestResultT", _build_result(data, request.response_model))
