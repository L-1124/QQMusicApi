"""请求描述符与批量请求容器. 提供对 API 请求的抽象与调度."""

import copy
from collections.abc import Generator
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel
from tarsio import TarsDict
from typing_extensions import overload

from ..models.request import Credential
from .pagination import PagerMeta, RefreshMeta, ResponsePager, ResponseRefresher
from .versioning import Platform

if TYPE_CHECKING:
    from .client import Client


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
RequestResultT = TypeVar("RequestResultT", bound=BaseModel | dict[str, Any] | TarsDict)


@overload
def _build_result(
    raw: TarsDict | dict[str, Any],
    response_model: type["ResponseModel"],
) -> "ResponseModel": ...


@overload
def _build_result(
    raw: dict[str, Any],
    response_model: None,
) -> dict[str, Any]: ...


@overload
def _build_result(
    raw: TarsDict,
    response_model: None,
) -> TarsDict: ...


def _build_result(
    raw: TarsDict | dict[str, Any],
    response_model: type[BaseModel] | None,
) -> BaseModel | dict[str, Any] | TarsDict:
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


@dataclass(kw_only=True)
class Request(Generic[RequestResultT]):
    """请求描述符."""

    _client: "Client"
    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]
    response_model: type[BaseModel] | None = None
    comm: dict[str, int | str | bool] | None = None
    is_jce: bool = False
    preserve_bool: bool = False
    credential: Credential | None = None
    platform: Platform | None = None

    def __await__(self) -> Generator[Any, Any, RequestResultT]:
        """使 Request 对象可被 await 执行."""
        return self._client.execute(self).__await__()

    def replace(self, **changes: Any) -> "Request[RequestResultT]":
        """返回一个应用了修改的新 Request 对象, 不会修改原对象."""
        if "param" not in changes:
            changes["param"] = copy.deepcopy(self.param)
        if "comm" not in changes and self.comm is not None:
            changes["comm"] = copy.deepcopy(self.comm)
        return dc_replace(self, **changes)


@dataclass
class PaginatedRequest(Request[RequestResultT]):
    """声明了连续翻页能力的请求描述符."""

    pager_meta: PagerMeta

    def get_pager_meta(self) -> PagerMeta:
        """返回连续翻页元数据."""
        return self.pager_meta

    def paginate(self, limit: int | None = None) -> ResponsePager[RequestResultT]:
        """返回响应的分页迭代器.

        Args:
            limit: 最大获取页数.
        """
        return ResponsePager(self, limit=limit)


@dataclass
class RefreshableRequest(Request[RequestResultT]):
    """声明了换一批能力的请求描述符."""

    refresh_meta: RefreshMeta

    def get_refresh_meta(self) -> RefreshMeta:
        """返回换一批元数据."""
        return self.refresh_meta

    def refresh(self) -> ResponseRefresher[RequestResultT]:
        """返回响应的换一批控制器."""
        return ResponseRefresher(self)
