"""Web 路由 Adapter 注册表."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .route_types import RouteContext

AdapterFn = Callable[["RouteContext"], "Awaitable[Any] | Any"]

_REGISTRY: dict[str, AdapterFn] = {}


def adapter(module: str, method: str) -> Callable[[AdapterFn], AdapterFn]:
    """将函数注册为指定 module.method 的 Web Adapter.

    与在 WebRoute 中内联 adapter= 等价, 但无需在 routes 文件中 import adapter 函数.
    inline adapter= 声明的优先级高于此注册表.

    Args:
        module: 模块名, 对应 modules.MODULE_TYPES 的 key.
        method: SDK 方法名或 adapter-only 路由的虚拟名.

    Returns:
        原样返回被装饰的函数.

    Raises:
        RuntimeError: 同一 module.method 重复注册时抛出.
    """

    def decorator(fn: AdapterFn) -> AdapterFn:
        key = f"{module}.{method}"
        if key in _REGISTRY:
            raise RuntimeError(f"Adapter 重复注册: {key}, 请检查是否存在重复定义")
        _REGISTRY[key] = fn
        return fn

    return decorator


def get_adapter(module: str, method: str) -> AdapterFn | None:
    """查找已注册的 Adapter.

    Args:
        module: 模块名.
        method: 方法名.

    Returns:
        已注册的 Adapter 函数, 或 None.
    """
    return _REGISTRY.get(f"{module}.{method}")


def registered_adapters() -> dict[str, AdapterFn]:
    """返回所有已注册 Adapter 的只读副本."""
    return dict(_REGISTRY)
