"""测试断言辅助函数."""

from collections.abc import Mapping
from typing import Any


def assert_request_shape(request_obj: Any, module: str, method: str) -> None:
    """断言请求对象的 module 和 method."""
    assert request_obj.module == module
    assert request_obj.method == method


def assert_param_contains(param: Mapping[object, Any], expected: Mapping[object, Any]) -> None:
    """断言参数字典包含预期键值."""
    for key, value in expected.items():
        assert key in param
        assert param[key] == value
