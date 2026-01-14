"""Client"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import httpx

from .utils.credential import Credential
from .utils.qimei import get_qimei
from .utils.sign import sign

logger = logging.getLogger("qqmusicapi.client")

T = TypeVar("T")


@dataclass
class RequestItem(Generic[T]):
    """单个请求项"""

    module: str
    method: str
    param: dict[str, Any]
    processor: Callable[[dict[str, Any]], T] | None = None
    key: str = ""


class Client:
    """QQMusic API Client"""

    UA_DEFAULT = "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54"
    VERSION = "13.2.5.8"
    VERSION_CODE = 13020508
    HOST = "y.qq.com"

    def __init__(
        self,
        credential: Credential | None = None,
        enable_sign: bool = False,
        timeout: int = 10,
        proxy: str | None = None,
    ):
        self.credential = credential or Credential()
        self.enable_sign = enable_sign

        self.http = httpx.AsyncClient(
            http2=True,
            timeout=timeout,
            proxy=proxy,
            headers={
                "User-Agent": self.UA_DEFAULT,
                "Referer": self.HOST,
            },
        )

        self.qimei = get_qimei(self.VERSION)["q36"]
        self.endpoint = "https://u.y.qq.com/cgi-bin/musicu.fcg"
        self.enc_endpoint = "https://u.y.qq.com/cgi-bin/musics.fcg"

    async def request(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        credential: Credential | None = None,
        common_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送 API 请求"""
        req_data_map = {
            f"{module}.{method}": {
                "module": module,
                "method": method,
                "param": param,
            }
        }

        resp_data = await self.batch_request(req_data_map, credential=credential, common_params=common_params)

        # 提取结果
        inner_data = resp_data.get(f"{module}.{method}", {})

        # 简单错误检查
        code = inner_data.get("code", 0)
        if code != 0:
            logger.warning(f"API Warning {code} in {module}.{method}: {inner_data.get('msg', 'Unknown error')}")

        return inner_data.get("data", inner_data)

    async def batch_request(
        self,
        req_data_map: dict[str, dict[str, Any]],
        *,
        credential: Credential | None = None,
        common_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送批量 API 请求"""
        cred = credential or self.credential

        # 公共参数
        common = {
            "cv": self.VERSION_CODE,
            "v": self.VERSION_CODE,
            "QIMEI36": self.qimei,
            "ct": "11",
            "tmeAppID": "qqmusic",
            "format": "json",
            "inCharset": "utf-8",
            "outCharset": "utf-8",
            "uid": "3931641530",
        }

        if common_params:
            common.update(common_params)

        if cred.has_musicid() and cred.has_musickey():
            common.update(
                {
                    "qq": str(cred.musicid),
                    "authst": cred.musickey,
                    "tmeLoginType": str(cred.login_type),
                }
            )

            # 设置 cookies
            cookies = httpx.Cookies()
            cookies.set("uin", str(cred.musicid), domain=".qq.com")
            cookies.set("qqmusic_key", cred.musickey, domain=".qq.com")
            cookies.set("qm_keyst", cred.musickey, domain=".qq.com")
            cookies.set("tmeLoginType", str(cred.login_type), domain=".qq.com")
            self.http.cookies = cookies

        # 构造请求数据
        req_data = {"comm": common, **req_data_map}

        url = self.enc_endpoint if self.enable_sign else self.endpoint
        request_kwargs = {"url": url, "json": req_data}

        if self.enable_sign:
            request_kwargs["params"] = {"sign": sign(req_data)}

        logger.debug(f"Batch Request: {list(req_data_map.keys())}")

        response = await self.http.post(**request_kwargs)
        response.raise_for_status()

        return response.json()

    async def close(self):
        """关闭 HTTP 连接"""
        await self.http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class RequestGroup:
    """批量请求组"""

    def __init__(
        self,
        client: Client | None = None,
        common_params: dict[str, Any] | None = None,
        limit: int = 20,
    ):
        """Args:
        client: 可选的 Client 实例,如果不需要立即 execute 可不传
        common_params: 组级别的公共参数
        limit: 单次请求合并的最大请求数
        """
        self.client = client
        self.common_params = common_params or {}
        self.limit = limit
        self._items: list[RequestItem] = []

    def add(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        processor: Callable[[dict[str, Any]], T] | None = None,
    ) -> RequestItem[T]:
        """添加一个请求到组中"""
        # 生成唯一 key
        idx = len(self._items)
        key = f"{module}.{method}.{idx}"

        item = RequestItem(
            module=module,
            method=method,
            param=param,
            processor=processor,
            key=key,
        )
        self._items.append(item)
        return item

    async def execute(self, client: Client | None = None) -> list[Any]:
        """执行所有请求并返回结果列表"""
        active_client = client or self.client
        if not active_client:
            raise ValueError("No client provided for execution")

        if not self._items:
            return []

        # 分批处理
        batches = [self._items[i : i + self.limit] for i in range(0, len(self._items), self.limit)]

        # 并行执行所有 batch
        tasks = [self._execute_batch(active_client, batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        # 展平结果
        flat_results = []
        for batch_res in batch_results:
            flat_results.extend(batch_res)

        return flat_results

    async def _execute_batch(self, client: Client, items: list[RequestItem]) -> list[Any]:
        """执行单个批次"""
        if not items:
            return []

        # 构建 req_data_map
        req_data_map = {}
        for item in items:
            req_data_map[item.key] = {
                "module": item.module,
                "method": item.method,
                "param": item.param,
            }

        # 发送请求
        resp_data = await client.batch_request(req_data_map, common_params=self.common_params)

        # 解析结果
        results = []
        for item in items:
            item_resp = resp_data.get(item.key, {})
            # 提取 data
            data = item_resp.get("data", item_resp)

            # 处理器
            if item.processor:
                try:
                    res = item.processor(data)
                except Exception as e:
                    logger.warning(f"Processor error for {item.key}: {e}")
                    res = None
                results.append(res)
            else:
                results.append(data)

        return results
