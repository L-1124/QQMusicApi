"""辅助功能工具入口."""

import hashlib
import time
import typing
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
from anyio import to_thread

from ..core.exceptions import ApiDataError
from ..models.helper import (
    FinishUploadResultDict,
    InitUploadFileDict,
    InitUploadResponse,
    UploadObjectInfo,
)
from ..models.request import Credential

if typing.TYPE_CHECKING:
    import os

    from .helper import BUSINESS_TYPE, HelperApi

# 分块上传阈值
_MULTIPART_THRESHOLD = 5 * 1024 * 1024  # 5MB
# COS 上传重试次数
_UPLOAD_RETRIES = 3
# 可重试的 HttpStatus
_RETRY_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


@dataclass(slots=True)
class UploadFileSession:
    """封装 COS 文件上传流程的会话对象.

    Args:
        api: HelperApi 实例.
        bus_id: 上传业务 ID.
        credential: 可选的凭证对象, 若不提供则使用全局的客户端凭证.
        max_concurrency: 最大并发上传数, 默认 3, 可根据网络环境调整.
    """

    api: "HelperApi"
    bus_id: "BUSINESS_TYPE"
    credential: Credential | None = None
    max_concurrency: int = 3

    _init_data: InitUploadResponse | None = field(default=None, init=False)
    _last_file_shas: tuple[str, ...] | None = field(default=None, init=False)

    async def _get_file_info(self, path: anyio.Path) -> InitUploadFileDict:
        """获取单个文件的信息用于 InitUpload."""
        if not await path.is_file():
            raise FileNotFoundError(f"文件不存在: {path}")

        stat = await path.stat()
        file_size = stat.st_size
        sha1_obj = hashlib.sha1()
        async with await path.open("rb") as f:
            while chunk := await f.read(8192):
                sha1_obj.update(chunk)

        return {
            "FileSha1": sha1_obj.hexdigest(),
            "FileName": path.name,
            "FileSize": file_size,
        }

    def _upload_to_cos(
        self,
        file_path: Path,
        region: str,
        secret_id: str,
        secret_key: str,
        token: str,
        bucket_name: str,
        object_key: str,
        file_size: int = 0,
    ) -> dict[str, Any]:
        """执行单个 COS 上传的同步方法, 支持分块上传与自动重试."""
        try:
            from qcloud_cos import CosConfig, CosS3Client
            from qcloud_cos.cos_exception import CosClientError, CosServiceError
        except ImportError as exc:
            raise ImportError("请先安装 `cos-python-sdk-v5` 库以支持文件直传.") from exc

        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Token=token,
            Scheme="https",
        )
        use_multipart = file_size > _MULTIPART_THRESHOLD
        s3_client = CosS3Client(config)

        for attempt in range(_UPLOAD_RETRIES + 1):
            try:
                if use_multipart:
                    resp = s3_client.upload_file(
                        Bucket=bucket_name,
                        LocalFilePath=str(file_path),
                        Key=object_key,
                        StorageClass="STANDARD",
                        EnableMD5=False,
                    )
                else:
                    with open(file_path, "rb") as fp:
                        resp = s3_client.put_object(
                            Bucket=bucket_name,
                            Body=fp,
                            Key=object_key,
                            StorageClass="STANDARD",
                            EnableMD5=False,
                        )
                return dict(resp)
            except CosServiceError as e:  # noqa: PERF203
                if attempt < _UPLOAD_RETRIES and e.get_status_code() in _RETRY_HTTP_STATUSES:
                    time.sleep(2**attempt)
                    continue
                raise
            except CosClientError:
                if attempt < _UPLOAD_RETRIES:
                    time.sleep(2**attempt)
                    continue
                raise

        raise RuntimeError("Upload to COS failed after max retries")

    async def prepare(self, file_paths: Sequence[str | Path]) -> None:
        """准备上传,获取或复用有效的临时凭证(按文件 SHA1 去重)."""
        paths = tuple(Path(p) for p in file_paths)
        if not paths:
            raise ValueError("至少需要提供一个文件路径.")

        file_info_map: dict[int, InitUploadFileDict] = {}
        async with anyio.create_task_group() as tg:

            async def _get_info(idx: int, p: anyio.Path):
                file_info_map[idx] = await self._get_file_info(p)

            for i, p in enumerate(paths):
                tg.start_soon(_get_info, i, anyio.Path(p))

        file_infos = [file_info_map[i] for i in range(len(paths))]
        current_shas = tuple(info["FileSha1"] for info in file_infos)

        if self._last_file_shas != current_shas:
            self._init_data = None
            self._last_file_shas = current_shas

        if self._init_data is not None:
            now = int(time.time())
            # 留 10 分钟余量防止临界过期
            if now < self._init_data.auth_info.expired_time - 600:
                return

        self._init_data = await self.api.init_upload(
            bus_id=self.bus_id,
            files=list(file_infos),
            credential=self.credential,
        )

    async def upload(
        self,
        file_paths: str | Path | Sequence[str | Path],
    ) -> list[UploadObjectInfo]:
        """执行多文件的完整上传流程.

        Args:
            file_paths: 单个或多个文件路径.

        Returns:
            list[UploadObjectInfo]: 所有文件上传成功后的信息列表.
        """
        if isinstance(file_paths, str | Path):
            file_paths = [file_paths]

        await self.prepare(file_paths)

        if self._init_data is None:
            raise ApiDataError("获取上传凭证失败: 服务器未返回凭证信息")

        auth_info = self._init_data.auth_info
        files_info = self._init_data.files

        if not files_info or len(files_info) != len(file_paths):
            raise ValueError("InitUpload 返回的文件目标数量不匹配.")

        secret_id = auth_info.secret_id
        secret_key = auth_info.secret_key
        token = auth_info.token

        # 并发直传 COS
        semaphore = anyio.Semaphore(self.max_concurrency)

        async def _upload_worker(
            path: Path,
            region: str,
            secret_id: str,
            secret_key: str,
            token: str,
            bucket_name: str,
            object_key: str,
            file_size: int = 0,
        ) -> None:
            async with semaphore:
                await to_thread.run_sync(
                    self._upload_to_cos,
                    path,
                    region,
                    secret_id,
                    secret_key,
                    token,
                    bucket_name,
                    object_key,
                    file_size,
                )

        finish_results: list[FinishUploadResultDict] = []

        stat_map: dict[int, os.stat_result] = {}
        async with anyio.create_task_group() as tg:

            async def _get_stat(idx: int, p: str | Path):
                stat_map[idx] = await anyio.Path(p).stat()

            for i, p in enumerate(file_paths):
                tg.start_soon(_get_stat, i, p)

        async with anyio.create_task_group() as tg:
            for i, file_info in enumerate(files_info):
                buckets = file_info.buckets
                if not buckets:
                    raise ApiDataError(f"获取上传凭证失败: 文件 {file_paths[i]} 未返回目标存储桶信息.")

                target_bucket = buckets[0]
                bucket_info = target_bucket.bucket
                bucket_name = bucket_info.name
                region = bucket_info.region
                object_key = file_info.object_key
                upload_status = target_bucket.upload_status
                stat = stat_map.get(i)
                fsize = stat.st_size if stat is not None else 0

                if not all([secret_id, secret_key, token, object_key, bucket_name, region]):
                    raise ApiDataError(f"获取上传凭证失败: 文件 {file_paths[i]} 上传凭证信息不完整.")

                if upload_status != 1:
                    tg.start_soon(
                        _upload_worker,
                        Path(file_paths[i]),
                        region,
                        secret_id,
                        secret_key,
                        token,
                        bucket_name,
                        object_key,
                        fsize,
                    )

                finish_results.append(
                    {
                        "Storage": {"Bucket": {"Name": bucket_name, "Region": region}, "ObjectKey": object_key},
                        "UploadResult": 0,
                    }
                )
        finish_data = await self.api.finish_upload(
            bus_id=self.bus_id,
            results=finish_results,
            credential=self.credential,
        )
        objects = finish_data.objects
        if not objects:
            raise ApiDataError("FinishUpload 未返回上传成功的文件对象.")
        return objects
