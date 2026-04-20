"""签名算法单元测试."""

import re

import pytest

from qqmusic_api.algorithms.sign import sign_request

# ---------------------------------------------------------------------------
# sign_request
# ---------------------------------------------------------------------------


def test_sign_request_returns_string() -> None:
    """测试 sign_request 返回字符串类型."""
    result = sign_request({"module": "test", "method": "test", "param": {}})
    assert isinstance(result, str)


def test_sign_request_starts_with_zzc() -> None:
    """测试签名结果以 'zzc' 开头."""
    result = sign_request({"module": "test", "method": "test", "param": {}})
    assert result.startswith("zzc")


def test_sign_request_is_lowercase() -> None:
    """测试签名结果全为小写字母和数字."""
    result = sign_request({"module": "test", "method": "test", "param": {}})
    assert result == result.lower()


def test_sign_request_deterministic() -> None:
    """测试相同请求体产生相同签名."""
    payload = {"module": "music.song", "method": "GetSongDetail", "param": {"song_id": 100}}
    assert sign_request(payload) == sign_request(payload)


def test_sign_request_different_payloads_differ() -> None:
    """测试不同请求体产生不同签名."""
    sig1 = sign_request({"module": "a", "method": "b", "param": {"x": 1}})
    sig2 = sign_request({"module": "a", "method": "b", "param": {"x": 2}})
    assert sig1 != sig2


def test_sign_request_empty_payload() -> None:
    """测试空字典输入不抛出异常且返回有效签名."""
    result = sign_request({})
    assert isinstance(result, str)
    assert result.startswith("zzc")


@pytest.mark.parametrize(
    "payload",
    [
        {"module": "m", "method": "f", "param": {}},
        {"module": "music.musichallAlbum.AlbumInfoServer", "method": "GetAlbumDetail", "param": {"albumId": 123}},
        {"a": [1, 2, 3], "b": {"nested": True}},
    ],
)
def test_sign_request_valid_format(payload: dict) -> None:
    """测试各种请求体签名格式合法."""
    result = sign_request(payload)
    assert re.match(r"^zzc[a-z0-9]+$", result) is not None
