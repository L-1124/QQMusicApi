"""工具函数单元测试."""

import re

import pytest

from qqmusic_api.utils.common import (
    bool_to_int,
    calc_md5,
    get_guid,
    get_searchID,
    hash33,
    parse_jsonpath,
)

# ---------------------------------------------------------------------------
# calc_md5
# ---------------------------------------------------------------------------


def test_calc_md5_empty_string() -> None:
    """测试空字符串的 MD5 值为标准值."""
    assert calc_md5("") == "d41d8cd98f00b204e9800998ecf8427e"


def test_calc_md5_known_value() -> None:
    """测试已知字符串的 MD5 值."""
    assert calc_md5("hello") == "5d41402abc4b2a76b9719d911017c592"


def test_calc_md5_bytes_input() -> None:
    """测试字节串输入与等效字符串产生相同的 MD5."""
    assert calc_md5(b"hello") == calc_md5("hello")


def test_calc_md5_multiple_args() -> None:
    """测试多个参数拼接计算 MD5 等同于合并后的字符串."""
    assert calc_md5("foo", "bar") == calc_md5("foobar")


def test_calc_md5_mixed_str_bytes() -> None:
    """测试字符串与字节串混合参数等同于合并后的字节串."""
    assert calc_md5("foo", b"bar") == calc_md5("foobar")


def test_calc_md5_unsupported_type_raises() -> None:
    """测试传入不支持类型时抛出 TypeError."""
    with pytest.raises(TypeError):
        calc_md5(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# get_guid
# ---------------------------------------------------------------------------


def test_get_guid_length() -> None:
    """测试 get_guid 返回 32 位十六进制字符串."""
    guid = get_guid()
    assert len(guid) == 32


def test_get_guid_hex_chars() -> None:
    """测试 get_guid 仅包含十六进制字符."""
    guid = get_guid()
    assert re.fullmatch(r"[0-9a-f]{32}", guid) is not None


def test_get_guid_unique() -> None:
    """测试连续调用 get_guid 返回不同值."""
    assert get_guid() != get_guid()


# ---------------------------------------------------------------------------
# hash33
# ---------------------------------------------------------------------------


def test_hash33_empty_string() -> None:
    """测试空字符串的哈希值等于初始值."""
    assert hash33("", h=0) == 0
    assert hash33("", h=5381) == 5381


def test_hash33_non_negative_result() -> None:
    """测试 hash33 始终返回非负整数."""
    assert hash33("any string") >= 0


def test_hash33_bounded() -> None:
    """测试 hash33 结果不超过 0x7FFFFFFF."""
    assert hash33("test") <= 2147483647


def test_hash33_deterministic() -> None:
    """测试相同输入产生相同哈希值."""
    assert hash33("hello") == hash33("hello")


@pytest.mark.parametrize("s", ["a", "abc", "musickey", "W_X_abc"])
def test_hash33_various_strings(s: str) -> None:
    """测试 hash33 对各种字符串返回整数."""
    result = hash33(s)
    assert isinstance(result, int)
    assert 0 <= result <= 2147483647


# ---------------------------------------------------------------------------
# bool_to_int
# ---------------------------------------------------------------------------


def test_bool_to_int_converts_true() -> None:
    """测试 bool_to_int 将 True 转为 1."""
    value: bool = True
    assert bool_to_int(value) == 1


def test_bool_to_int_converts_false() -> None:
    """测试 bool_to_int 将 False 转为 0."""
    value: bool = False
    assert bool_to_int(value) == 0


def test_bool_to_int_returns_non_bool_unchanged() -> None:
    """测试 bool_to_int 对非布尔值原样返回."""
    assert bool_to_int(42) == 42
    assert bool_to_int("hello") == "hello"
    assert bool_to_int(None) is None


def test_bool_to_int_dict_with_bool_values() -> None:
    """测试 bool_to_int 递归转换字典中的布尔值."""
    result = bool_to_int({"a": True, "b": False, "c": 1})
    assert result == {"a": 1, "b": 0, "c": 1}


def test_bool_to_int_dict_without_bool_returns_same_object() -> None:
    """测试 bool_to_int 对无布尔值的字典返回原对象."""
    d = {"x": 1, "y": "z"}
    assert bool_to_int(d) is d


def test_bool_to_int_list_with_bool_values() -> None:
    """测试 bool_to_int 递归转换列表中的布尔值."""
    result = bool_to_int([True, False, 2])
    assert result == [1, 0, 2]


def test_bool_to_int_list_without_bool_returns_same_object() -> None:
    """测试 bool_to_int 对无布尔值的列表返回原对象."""
    lst = [1, 2, 3]
    assert bool_to_int(lst) is lst


def test_bool_to_int_nested_structure() -> None:
    """测试 bool_to_int 递归处理嵌套结构."""
    result = bool_to_int({"a": [True, {"b": False}]})
    assert result == {"a": [1, {"b": 0}]}


# ---------------------------------------------------------------------------
# get_searchID
# ---------------------------------------------------------------------------


def test_get_search_id_is_string() -> None:
    """测试 get_searchID 返回字符串类型."""
    sid = get_searchID()
    assert isinstance(sid, str)


def test_get_search_id_numeric_string() -> None:
    """测试 get_searchID 返回纯数字字符串."""
    sid = get_searchID()
    assert sid.isdigit()


def test_get_search_id_unique() -> None:
    """测试连续调用 get_searchID 产生不同值的概率极高."""
    ids = {get_searchID() for _ in range(10)}
    assert len(ids) > 1


# ---------------------------------------------------------------------------
# parse_jsonpath
# ---------------------------------------------------------------------------


def test_parse_jsonpath_returns_compiled_expr() -> None:
    """测试 parse_jsonpath 返回可用的 JSONPath 表达式对象."""
    expr = parse_jsonpath("$.foo")
    result = [m.value for m in expr.find({"foo": 42})]
    assert result == [42]


def test_parse_jsonpath_caches_result() -> None:
    """测试 parse_jsonpath 对相同表达式返回同一对象."""
    expr1 = parse_jsonpath("$.bar")
    expr2 = parse_jsonpath("$.bar")
    assert expr1 is expr2


def test_parse_jsonpath_nested_expression() -> None:
    """测试 parse_jsonpath 支持嵌套路径表达式."""
    expr = parse_jsonpath("$.a.b")
    result = [m.value for m in expr.find({"a": {"b": "nested"}})]
    assert result == ["nested"]
