"""CGI 与 HTTP 请求准备器单元测试 (桩依赖驱动, 不发起真实网络)."""

from typing import Any, cast

import orjson as json
import pytest
import pytest_asyncio

from qqmusic_api.algorithms import zzc_sign
from qqmusic_api.core.preparation import CgiBatch, CgiBatchKey, CgiPreparer, HttpPreparer
from qqmusic_api.core.request import CgiRequest, HttpRequest
from qqmusic_api.core.runtime import ClientDefaults, RequestScope, ScopedCall, resolve_scope
from qqmusic_api.core.transport import PreparedRequest
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.utils.device import DeviceManager

pytestmark = pytest.mark.core


class StubQimeiManager:
    """返回固定 QIMEI 并记录调用次数的桩管理器."""

    def __init__(self) -> None:
        """初始化调用计数."""
        self.calls = 0

    async def get_cached(self) -> dict[str, str]:
        """返回固定 QIMEI 字典并计数."""
        self.calls += 1
        return {"q16": "test_q16", "q36": "test_q36"}


class StubAndroidSessionManager:
    """记录 ensure 调用的桩会话管理器."""

    def __init__(self) -> None:
        """初始化调用记录."""
        self.calls: list[RequestScope] = []

    async def ensure(self, scope: RequestScope) -> None:
        """记录一次 ensure 调用."""
        self.calls.append(scope)


class PreparerCarrier:
    """CGI 准备器及其依赖桩的测试载体."""

    def __init__(
        self,
        preparer: CgiPreparer,
        qimei: StubQimeiManager,
        android_session: StubAndroidSessionManager,
        device_store: DeviceManager,
    ) -> None:
        """保存准备器与依赖桩."""
        self.preparer = preparer
        self.qimei = qimei
        self.android_session = android_session
        self.device_store = device_store


class _NoopRequest:
    """无覆盖字段的请求桩."""

    credential: Credential | None = None
    platform: Platform | None = None


def _defaults(platform: Platform = Platform.WEB, credential: Credential | None = None) -> ClientDefaults:
    """构造测试用客户端默认值."""
    return ClientDefaults(
        credential=credential or Credential(musicid=1, musickey="global"),
        platform=platform,
        version_policy=DEFAULT_VERSION_POLICY,
    )


def _scope(platform: Platform = Platform.WEB, credential: Credential | None = None) -> RequestScope:
    """构造测试用请求快照."""
    return resolve_scope(_NoopRequest(), _defaults(platform, credential))


def _batch(requests: list[Any], scope: RequestScope) -> CgiBatch:
    """以运行时快照构造 CgiBatch 批次."""
    return CgiBatch(
        scope=scope, calls=tuple(ScopedCall(index=i, request=req, scope=scope) for i, req in enumerate(requests))
    )


def _call(request: Any, scope: RequestScope) -> ScopedCall:
    """以运行时快照构造单条 ScopedCall."""
    return ScopedCall(index=0, request=request, scope=scope)


def _cgi_request(**kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    kwargs.setdefault("module", "test.module")
    kwargs.setdefault("method", "test_method")
    kwargs.setdefault("param", {})
    return CgiRequest(_client=cast("Any", None), **kwargs)


def _http_request(**kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    kwargs.setdefault("method", "GET")
    kwargs.setdefault("url", "https://example.com/api")
    return HttpRequest(_client=cast("Any", None), **kwargs)


@pytest_asyncio.fixture
async def carrier() -> PreparerCarrier:
    """创建注入桩依赖的 CGI 准备器载体."""
    qimei = StubQimeiManager()
    android_session = StubAndroidSessionManager()
    device_store = DeviceManager(None)
    await device_store.get_device()
    preparer = CgiPreparer(
        android_session=cast("Any", android_session),
        device_store=device_store,
        qimei_manager=cast("Any", qimei),
        version_policy=DEFAULT_VERSION_POLICY,
    )
    return PreparerCarrier(preparer, qimei, android_session, device_store)


@pytest.fixture
def http_preparer() -> HttpPreparer:
    """创建 HTTP 准备器."""
    return HttpPreparer(device_store=DeviceManager(None), version_policy=DEFAULT_VERSION_POLICY)


# ---------------------------------------------------------------------------
# CgiPreparer
# ---------------------------------------------------------------------------


async def test_prepare_batch_bool_conversion(carrier: PreparerCarrier):
    """测试默认将参数中的布尔值转换为整数."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request(param={"flag": True, "n": 1})], _scope()))
    sub = prepared.kwargs["json"]["req_0"]
    assert sub["param"]["flag"] == 1
    assert sub["param"]["n"] == 1


async def test_prepare_batch_preserve_bool(carrier: PreparerCarrier):
    """测试 preserve_bool 保留参数中的布尔值."""
    prepared = await carrier.preparer.prepare_batch(
        _batch([_cgi_request(param={"flag": True}, preserve_bool=True)], _scope())
    )
    assert prepared.kwargs["json"]["req_0"]["param"]["flag"] is True


async def test_prepare_batch_comm_merge_user_wins(carrier: PreparerCarrier):
    """测试用户 comm 合并时覆盖同名键并保留默认键."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request(comm={"cv": 999, "extra": "y"})], _scope()))
    comm = prepared.kwargs["json"]["comm"]
    assert comm["cv"] == 999
    assert comm["extra"] == "y"
    assert comm["ct"] == 24


async def test_prepare_batch_override_comm(carrier: PreparerCarrier):
    """测试 override_comm 时 comm 完全替换为自定义参数."""
    prepared = await carrier.preparer.prepare_batch(
        _batch([_cgi_request(comm={"custom": "x"}, override_comm=True)], _scope())
    )
    assert prepared.kwargs["json"]["comm"] == {"custom": "x"}


async def test_prepare_batch_web_skips_qimei_and_session(carrier: PreparerCarrier):
    """测试 WEB 平台不获取 QIMEI 也不刷新 Android 会话."""
    await carrier.preparer.prepare_batch(_batch([_cgi_request()], _scope(Platform.WEB)))
    assert carrier.qimei.calls == 0
    assert carrier.android_session.calls == []


async def test_prepare_batch_android_ensures_session_and_qimei(carrier: PreparerCarrier):
    """测试 ANDROID 平台刷新会话并获取 QIMEI 注入 comm."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request()], _scope(Platform.ANDROID)))
    assert len(carrier.android_session.calls) == 1
    assert carrier.qimei.calls == 1
    comm = prepared.kwargs["json"]["comm"]
    assert comm["QIMEI"] == "test_q16"
    assert comm["QIMEI36"] == "test_q36"
    assert prepared.kwargs["headers"]["User-Agent"].startswith("QQMusic ")


async def test_prepare_batch_web_user_agent(carrier: PreparerCarrier):
    """测试 WEB 平台使用 Chrome UA."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request()], _scope(Platform.WEB)))
    assert prepared.kwargs["headers"]["User-Agent"] == (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


async def test_prepare_batch_sign_url(carrier: PreparerCarrier):
    """测试签名模式切换 URL 并生成时间戳与 zzc 签名."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request(sign=True)], _scope()))
    payload = prepared.kwargs["json"]
    params = prepared.kwargs["params"]
    assert prepared.url == "https://u.y.qq.com/cgi-bin/musics.fcg"
    assert int(params["_"]) > 0
    assert params["sign"] == zzc_sign(json.dumps(payload))


async def test_prepare_batch_unsigned_url(carrier: PreparerCarrier):
    """测试默认使用 musicu.fcg 且无签名参数."""
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request()], _scope()))
    assert prepared.url == "https://u.y.qq.com/cgi-bin/musicu.fcg"
    assert prepared.kwargs["params"] == {}


async def test_prepare_batch_multiple_requests_indexed(carrier: PreparerCarrier):
    """测试多个请求按序写入 req_0 与 req_1."""
    first = _cgi_request(module="m1")
    second = _cgi_request(module="m2", param={"x": 1})
    prepared = await carrier.preparer.prepare_batch(_batch([first, second], _scope()))
    payload = prepared.kwargs["json"]
    assert payload["req_0"]["module"] == "m1"
    assert payload["req_1"]["module"] == "m2"
    assert payload["req_1"]["param"] == {"x": 1}


async def test_prepare_batch_require_login_without_credential(carrier: PreparerCarrier):
    """测试 require_login 且凭证无效时由执行器逐项校验 (准备器不再重复校验)."""
    scope = _scope(credential=Credential())
    # 准备器只接收已通过登录校验的批次; 登录校验职责在 CgiExecutor.
    prepared = await carrier.preparer.prepare_batch(_batch([_cgi_request(require_login=True)], scope))
    assert prepared.method == "POST"


async def test_prepare_batch_accepts_heterogeneous_calls_without_revalidation(carrier: PreparerCarrier):
    """测试准备器不做二次分组校验 (分组职责在 CgiExecutor)."""
    mixed = [
        _cgi_request(sign=False),
        _cgi_request(sign=True),
    ]
    prepared = await carrier.preparer.prepare_batch(_batch(mixed, _scope()))
    assert prepared.kwargs["json"]["req_0"]["module"] == "test.module"
    assert prepared.kwargs["json"]["req_1"]["module"] == "test.module"


# ---------------------------------------------------------------------------
# CgiBatchKey
# ---------------------------------------------------------------------------


def test_batch_key_credential_fingerprint_distinguishes_extra_fields():
    """测试凭证指纹覆盖全部字段而非仅 musicid/musickey."""
    base = _call(_cgi_request(), _scope(credential=Credential(musicid=1, musickey="key", refresh_token="a")))
    other = _call(_cgi_request(), _scope(credential=Credential(musicid=1, musickey="key", refresh_token="b")))
    assert CgiBatchKey.from_call(base) != CgiBatchKey.from_call(other)


def test_batch_key_equal_for_same_credential():
    """测试相同凭证生成相同分组键."""
    cred = Credential(musicid=2, musickey="k")
    first = _call(_cgi_request(), _scope(credential=cred))
    second = _call(_cgi_request(), _scope(credential=cred.model_copy(deep=True)))
    assert CgiBatchKey.from_call(first) == CgiBatchKey.from_call(second)


def test_batch_key_none_and_empty_comm_merge():
    """测试 None 与空 dict comm 规范化一致 (可合批)."""
    scope = _scope()
    none_comm = _call(_cgi_request(), scope)
    empty_comm = _call(_cgi_request(comm={}), scope)
    assert CgiBatchKey.from_call(none_comm) == CgiBatchKey.from_call(empty_comm)


def test_batch_key_nested_comm_stable_serialization():
    """测试嵌套 comm 不同键序序列化为相同分组键."""
    scope = _scope()
    first = _cgi_request(comm={"outer": {"z": 1, "y": 2}})
    second = _cgi_request(comm={"outer": {"y": 2, "z": 1}})
    assert CgiBatchKey.from_call(_call(first, scope)) == CgiBatchKey.from_call(_call(second, scope))


def test_batch_key_ignores_preserve_bool_and_parse_options():
    """测试 preserve_bool 与解析选项不进入分组键."""
    scope = _scope()
    base = _cgi_request()
    variant = _cgi_request(preserve_bool=True, allow_error_codes=(1,), parse_on_allow=True, disable_parse=True)
    assert CgiBatchKey.from_call(_call(base, scope)) == CgiBatchKey.from_call(_call(variant, scope))


def test_batch_key_separates_sign_and_comm():
    """测试 sign, comm 与 override_comm 差异产生不同分组键."""
    scope = _scope()
    base = _cgi_request()
    assert CgiBatchKey.from_call(_call(base, scope)) != CgiBatchKey.from_call(_call(_cgi_request(sign=True), scope))
    assert CgiBatchKey.from_call(_call(base, scope)) != CgiBatchKey.from_call(_call(_cgi_request(comm={"a": 1}), scope))
    assert CgiBatchKey.from_call(_call(base, scope)) != CgiBatchKey.from_call(
        _call(_cgi_request(comm={"a": 1}, override_comm=True), scope)
    )


# ---------------------------------------------------------------------------
# HttpPreparer
# ---------------------------------------------------------------------------


async def test_http_prepare_injects_cookies(http_preparer: HttpPreparer):
    """测试 scope 凭证注入 Cookies 且 str_musicid 优先."""
    request = _http_request()
    scope = _scope(credential=Credential(musicid=123, str_musicid="456", musickey="key"))
    prepared = await http_preparer.prepare(_call(request, scope))
    cookies = prepared.kwargs["cookies"]
    assert cookies["uin"] == "456"
    assert cookies["qqmusic_uin"] == "456"
    assert cookies["qm_keyst"] == "key"
    assert cookies["qqmusic_key"] == "key"


async def test_http_prepare_user_cookies_override(http_preparer: HttpPreparer):
    """测试用户 cookies 覆盖凭证注入的同名键."""
    request = _http_request(cookies={"uin": "custom", "extra": "x"})
    scope = _scope(credential=Credential(musicid=123, musickey="key"))
    prepared = await http_preparer.prepare(_call(request, scope))
    cookies = prepared.kwargs["cookies"]
    assert cookies["uin"] == "custom"
    assert cookies["extra"] == "x"
    assert cookies["qm_keyst"] == "key"


async def test_http_prepare_no_credential_no_cookies(http_preparer: HttpPreparer):
    """测试无凭证时不注入 cookies."""
    prepared = await http_preparer.prepare(_call(_http_request(), _scope(credential=Credential())))
    assert "cookies" not in prepared.kwargs


async def test_http_prepare_default_web_ua(http_preparer: HttpPreparer):
    """测试缺少 UA 时注入 WEB 平台 UA."""
    prepared = await http_preparer.prepare(_call(_http_request(), _scope()))
    assert prepared.kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0")


async def test_http_prepare_respects_existing_ua(http_preparer: HttpPreparer):
    """测试已有 User-Agent 不被覆盖."""
    request = _http_request(headers={"User-Agent": "custom-ua"})
    prepared = await http_preparer.prepare(_call(request, _scope()))
    assert prepared.kwargs["headers"]["User-Agent"] == "custom-ua"


async def test_http_prepare_passes_all_options(http_preparer: HttpPreparer):
    """测试全部 HTTP options 透传到准备结果."""
    request = _http_request(
        params={"q": 1},
        json={"body": True},
        kwargs={"timeout": 3.0, "allow_redirects": False, "stream": True, "auth": ("u", "p")},
    )
    prepared = await http_preparer.prepare(_call(request, _scope()))
    kwargs = prepared.kwargs
    assert kwargs["params"] == {"q": 1}
    assert kwargs["json"] == {"body": True}
    assert kwargs["timeout"] == 3.0
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["auth"] == ("u", "p")
    assert prepared.method == "GET"
    assert prepared.url == "https://example.com/api"


async def test_http_prepare_does_not_mutate_input(http_preparer: HttpPreparer):
    """测试准备过程不修改请求描述符中的原始字典."""
    headers = {"Accept": "application/json"}
    cookies = {"uin": "orig"}
    request = _http_request(headers=headers, cookies=cookies)
    scope = _scope(credential=Credential(musicid=9, musickey="k"))
    await http_preparer.prepare(_call(request, scope))
    assert headers == {"Accept": "application/json"}
    assert cookies == {"uin": "orig"}


def test_prepared_request_shape_matches_transport_contract():
    """测试准备结果具备传输协议要求的 method/url/kwargs 形状."""
    prepared = PreparedRequest(method="POST", url="https://x", kwargs={"json": {}})
    assert prepared.method == "POST"
    assert prepared.url == "https://x"
    assert prepared.kwargs == {"json": {}}
