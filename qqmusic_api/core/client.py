"""Client"""

import logging
import uuid
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

import anyio
import httpx
import orjson as json
from pydantic import BaseModel
from tarsio import Struct, TarsDict

from ..models import (
    CommonParams,
    Credential,
    JceRequest,
    JceRequestItem,
    JceResponse,
    JsonRequest,
    JsonRequestItem,
    JsonResponse,
)
from ..utils.common import bool_to_int, hash33
from ..utils.device import Device
from ..utils.qimei import QimeiResult, get_qimei
from .exceptions import ApiError, NetworkError, build_api_error, extract_api_error_code

if TYPE_CHECKING:
    from .request import Request, RequestGroup

R = TypeVar("R", bound=BaseModel | Struct | dict)


class RequestItem(TypedDict):
    """请求项"""

    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]


logger = logging.getLogger("qqmusicapi.client")


class Client:
    """QQMusic API Client."""

    def __init__(
        self,
        credential: Credential | None = None,
        enable_sign: bool = False,
        platform: str = "android",
        session: httpx.AsyncClient | None = None,
        max_concurrency: int = 10,
        max_connections: int = 20,
    ):
        self.credential = credential or Credential()
        self.device = Device()
        self.enable_sign = enable_sign
        self.platform = platform
        self._guid = uuid.uuid4().hex

        self._limiter = anyio.CapacityLimiter(max_concurrency)
        self._owns_session = session is None
        self._session = session or httpx.AsyncClient(
            http2=True,
            timeout=10.0,
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=max_connections,
                max_connections=max_connections,
            ),
        )

        self._qimei_lock = anyio.Lock()
        self._qimei_loaded = False
        self._qimei_cache: QimeiResult | None = None

    def using(self, credential: Credential) -> "Client":
        """创建共享连接配置的新 Client。"""
        new_client = object.__new__(Client)
        new_client.credential = credential
        new_client.device = self.device
        new_client.enable_sign = self.enable_sign
        new_client.platform = self.platform
        new_client._guid = self._guid
        new_client._limiter = self._limiter
        new_client._owns_session = False
        new_client._session = self._session
        new_client._qimei_lock = self._qimei_lock
        new_client._qimei_loaded = self._qimei_loaded
        new_client._qimei_cache = self._qimei_cache
        return new_client

    async def _request_raw(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发送原始 HTTP 请求。"""
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

    @staticmethod
    def _ensure_http_ok(resp: httpx.Response) -> None:
        """校验 HTTP 状态码。"""
        if resp.status_code != 200:
            raise ApiError("HTTP 请求失败", code=resp.status_code, data=resp.text[:500])

    @staticmethod
    def _parse_json_response(resp: httpx.Response) -> JsonResponse:
        """解析 JSON 响应。"""
        try:
            payload = json.loads(resp.content)
            return JsonResponse.model_validate(payload)
        except Exception as exc:
            raise ApiError(
                f"JSON 解析失败: {exc!s}",
                code=-1,
                data=resp.text[:500],
                cause=exc,
            ) from exc

    @staticmethod
    def _parse_jce_response(resp: httpx.Response) -> JceResponse:
        """解析 JCE 响应。"""
        try:
            return JceResponse.decode(resp.content)
        except Exception as exc:
            raise ApiError(
                f"JCE 响应解析失败: {exc!s}",
                code=-1,
                data=resp.text[:500] if isinstance(resp.text, str) else str(resp.content[:500]),
                cause=exc,
            ) from exc

    async def _get_qimei_cached(self) -> QimeiResult | None:
        """获取并缓存 QIMEI。"""
        if self._qimei_loaded:
            return self._qimei_cache

        async with self._qimei_lock:
            if self._qimei_loaded:
                return self._qimei_cache
            try:
                self._qimei_cache = await get_qimei("14.9.0.8", session=self._session)
            except Exception as exc:
                logger.warning("获取 QIMEI 失败: %s", exc)
                self._qimei_cache = None
            self._qimei_loaded = True
            return self._qimei_cache

    @staticmethod
    def _get_g_tk(credential: Credential) -> int:
        """计算 g_tk。"""
        if credential.musickey:
            return hash33(credential.musickey, 5381)
        return 5381

    async def _build_common_params(self, platform: str | None, credential: Credential) -> dict[str, Any]:
        """构建通用 comm 参数。"""
        target_platform = platform or self.platform

        if target_platform in {"android", "android_jce"}:
            qimei = await self._get_qimei_cached() or {}
            params = CommonParams(
                ct=11,
                cv=14090008,
                v=14090008,
                chid="2005000982",
                qq=str(credential.musicid) if credential.musicid else None,
                authst=credential.musickey or None,
                tmeLoginType=credential.login_type,
                QIMEI=qimei.get("q16", ""),
                QIMEI36=qimei.get("q36", ""),
                OpenUDID=self._guid,
                udid=self._guid,
                OpenUDID2=self._guid,
                aid=self.device.android_id,
                os_ver=self.device.version.release,
                phonetype=self.device.model,
                devicelevel=str(self.device.version.sdk),
                newdevicelevel=str(self.device.version.sdk),
                rom=self.device.fingerprint,
            )
        elif target_platform == "desktop":
            params = CommonParams(
                ct=20,
                cv=2201,
                platform="wk_v17",
                chid="0",
                uin=credential.musicid or None,
                g_tk=self._get_g_tk(credential),
                guid=self._guid.upper(),
            )
        else:
            g_tk = self._get_g_tk(credential)
            params = CommonParams(
                ct=24,
                cv=4747474,
                platform="yqq.json",
                chid="0",
                uin=credential.musicid,
                g_tk=g_tk,
                g_tk_new_20200303=g_tk,
            )

        comm = params.model_dump(by_alias=True, exclude_none=True)
        if target_platform == "android_jce":
            comm = {k: str(v) for k, v in comm.items()}
        return comm

    def build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type[R] | None = None,
        comm: dict[str, Any] | None = None,
        is_jce: bool = False,
        credential: Credential | None = None,
        platform: str | None = None,
    ) -> "Request[R]":
        """构建可 await 的请求描述符。"""
        from .request import Request

        return Request(
            _client=self,
            module=module,
            method=method,
            param=param,
            response_model=response_model,
            comm=comm,
            is_jce=is_jce,
            credential=credential,
            platform=platform,
        )

    def request_group(self, batch_size: int = 20, max_inflight_batches: int = 5) -> "RequestGroup":
        """创建批量请求容器。"""
        from .request import RequestGroup

        return RequestGroup(self, batch_size=batch_size, max_inflight_batches=max_inflight_batches)

    async def execute(self, request: "Request[R]") -> R:
        """执行单个请求描述符。"""
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
        """构建响应对象。"""
        if response_model is None:
            return raw
        if isinstance(response_model, type) and issubclass(response_model, BaseModel):
            return response_model.model_validate(raw)
        return raw

    async def close(self) -> None:
        """关闭底层会话。"""
        if self._owns_session:
            await self._session.aclose()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def _get_user_agent(self, platform: str | None = None) -> str:
        """根据模式生成 UA。"""
        target_platform = platform or self.platform
        if target_platform == "android":
            return f"QQMusic/14090008 (Android {self.device.version.release}; {self.device.model})"
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def _get_cookies(self, credential: Credential | None = None) -> dict[str, str]:
        """从 Credential 提取 Cookies。"""
        auth: dict[str, str] = {}
        cred = credential or self.credential
        if cred.musicid:
            auth["uin"] = str(cred.musicid)
            auth["qqmusic_uin"] = str(cred.musicid)
        if cred.musickey:
            auth["qm_keyst"] = cred.musickey
            auth["qqmusic_key"] = cred.musickey
        return auth

    async def fetch(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发送 HTTP 请求。"""
        return await self._request_raw(method, url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        credential: Credential | None = None,
        platform: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送请求 (自动携带 Cookies)。"""
        cookies = kwargs.get("cookies", {})
        auth_cookies = self._get_cookies(credential)
        kwargs["headers"] = kwargs.get("headers", {})
        kwargs["headers"]["User-Agent"] = self._get_user_agent(platform)
        if auth_cookies:
            auth_cookies.update(cookies)
            kwargs["cookies"] = auth_cookies

        logger.debug("发送请求: %s %s", method, url)
        return await self.fetch(method, url, **kwargs)

    async def request_musicu(
        self,
        data: RequestItem | list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        url: str = "https://u.y.qq.com/cgi-bin/musicu.fcg",
        platform: str | None = None,
    ) -> JsonResponse:
        """发送标准 QQ 音乐请求 (Musicu/JSON) 并解析。"""
        requests = data if isinstance(data, list) else [data]
        logger.debug("构建 JSON 批量请求: count=%s platform=%s", len(requests), platform or self.platform)

        cred = credential or self.credential
        base_comm = await self._build_common_params(platform, cred)
        if comm:
            base_comm.update(comm)

        payload = JsonRequest(
            comm=base_comm,
            data=[
                JsonRequestItem(
                    module=req["module"],
                    method=req["method"],
                    param=bool_to_int(req["param"]),
                )
                for req in requests
            ],
        ).model_dump(mode="plain")

        params: dict[str, str] = {}
        if self.enable_sign:
            from ..utils.sign import sign

            signature = sign(payload)
            if signature:
                params["sign"] = signature

        resp = await self.fetch("POST", url, json=payload, params=params)
        self._ensure_http_ok(resp)
        return self._parse_json_response(resp)

    async def request_jce(
        self,
        data: RequestItem | list[RequestItem],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        url: str = "http://u.y.qq.com/cgi-bin/musicw.fcg",
    ) -> JceResponse:
        """发送 JCE 格式的请求并解析。"""
        requests = data if isinstance(data, list) else [data]
        logger.debug("构建 JCE 批量请求: count=%s", len(requests))

        cred = credential or self.credential
        base_comm = await self._build_common_params("android_jce", cred)
        if comm:
            base_comm.update(comm)

        payload = JceRequest(
            base_comm,
            {
                f"req_{idx}": JceRequestItem(
                    module=req["module"],
                    method=req["method"],
                    param=TarsDict(bool_to_int(req["param"])),
                )
                for idx, req in enumerate(requests)
            },
        ).encode()

        resp = await self.fetch(
            "POST",
            url,
            content=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self._get_user_agent("android"),
                "x-sign-data-type": "jce",
            },
        )
        self._ensure_http_ok(resp)
        return self._parse_jce_response(resp)
