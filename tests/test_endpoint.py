"""端点元数据与请求描述符生成测试."""

import inspect

import pytest
from pydantic import BaseModel

from qqmusic_api.core.endpoint import (
    CgiEndpointMeta,
    CgiRequestData,
    HttpEndpointMeta,
    HttpRequestData,
    cgi_endpoint,
    get_endpoint_meta,
    http_endpoint,
)
from qqmusic_api.core.request import CgiRequest, HttpRequest
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.models.search import QuickSearchResponse, SearchByTypeResponse
from qqmusic_api.models.song import (
    GetSongDetailResponse,
    GetSongUrlsResponse,
)
from qqmusic_api.modules._base import ApiModule
from qqmusic_api.modules.search import SearchApi
from qqmusic_api.modules.song import (
    EVKEY_META,
    VKEY_META,
    EncryptedSongFileType,
    SongApi,
    SongFileInfo,
    SongFileType,
)

pytestmark = pytest.mark.core


class DummyModel(BaseModel):
    """用于测试的模型桩."""

    code: int = 0
    name: str = "test"


def _module_client(credential: Credential | None = None):
    """构造仅用于请求绑定的 Client 桩."""

    class StubClient:
        """提供绑定上下文的 Client 桩."""

        def __init__(self) -> None:
            """初始化默认请求上下文."""
            self.credential = credential or Credential()
            self.platform = Platform.ANDROID
            self.version_policy = DEFAULT_VERSION_POLICY

        async def execute(self, request):
            """拒绝测试意外执行网络请求."""
            raise AssertionError(f"不应执行请求: {request}")

    return StubClient()


def test_endpoint_decorator_preserves_signature_and_metadata():
    """验证 endpoint 装饰器保留原始函数签名文档与暴露元数据."""

    @cgi_endpoint(
        key="custom.sample_cgi_test",
        module="mod",
        method="met",
        platform=Platform.WEB,
        response_model=DummyModel,
    )
    def sample_cgi(self, user_id: int, *, flag: bool = False) -> CgiRequestData:
        """这是示例函数的文档."""
        return CgiRequestData(param={"user_id": user_id, "flag": flag})

    class SampleApi(ApiModule):
        """测试端点模块."""

        sample = sample_cgi

    bound_method = SampleApi(_module_client()).sample
    assert bound_method.__name__ == "sample_cgi"
    assert bound_method.__doc__ == "这是示例函数的文档."
    sig = inspect.signature(bound_method)
    assert list(sig.parameters.keys()) == ["user_id", "flag"]
    assert sig.return_annotation == CgiRequest[DummyModel]
    assert not hasattr(bound_method, "__wrapped__")
    meta = get_endpoint_meta(SampleApi.sample)
    assert meta.key == "custom.sample_cgi_test"
    assert isinstance(meta, CgiEndpointMeta)
    assert meta.platform == Platform.WEB
    assert meta.response_model is DummyModel

    request = bound_method(123, flag=True)
    assert isinstance(request, CgiRequest)
    assert request.module == "mod"
    assert request.method == "met"
    assert request.platform == Platform.WEB
    assert request.param == {"user_id": 123, "flag": True}
    assert request.response_model is DummyModel


def test_http_endpoint_decorator():
    """验证 http_endpoint 装饰器构建 HttpRequest."""

    @http_endpoint(
        key="custom.sample_http_test",
        method="POST",
        url_template="https://api.example.com/{user_id}/info",
        response_model=DummyModel,
    )
    def sample_http(self, user_id: int) -> HttpRequestData:
        """HTTP 示例方法."""
        return HttpRequestData(path_params={"user_id": user_id}, params={"format": "json"})

    class SampleHttpApi(ApiModule):
        """测试 HTTP 端点模块."""

        sample = sample_http

    bound_method = SampleHttpApi(_module_client()).sample
    meta = get_endpoint_meta(SampleHttpApi.sample)
    assert meta.key == "custom.sample_http_test"
    assert isinstance(meta, HttpEndpointMeta)
    assert meta.method == "POST"

    request = bound_method(456)
    assert isinstance(request, HttpRequest)
    assert request.method == "POST"
    assert request.url == "https://api.example.com/456/info"
    assert request.params == {"format": "json"}
    assert request.response_model is DummyModel


def test_get_detail_endpoint():
    """验证 get_detail 正确构建歌曲详情请求描述符."""
    api = SongApi(_module_client())
    req_num = api.get_detail(12345)
    assert isinstance(req_num, CgiRequest)
    assert req_num.module == "music.pf_song_detail_svr"
    assert req_num.method == "get_song_detail_yqq"
    assert req_num.platform == Platform.WEB
    assert req_num.response_model is GetSongDetailResponse
    assert req_num.param == {"song_id": 12345}

    req_str_id = api.get_detail("67890")
    assert req_str_id.param == {"song_id": 67890}

    req_mid = api.get_detail("0039MnYb0qxYAc")
    assert req_mid.param == {"song_mid": "0039MnYb0qxYAc"}


def test_get_song_urls_endpoint():
    """验证 get_song_urls 动态元数据选择与凭据提取."""
    api = SongApi(_module_client())
    info = [SongFileInfo(mid="0039MnYb0qxYAc")]
    req_normal = api.get_song_urls(info, file_type=SongFileType.MP3_128)
    assert req_normal.module == VKEY_META.module
    assert req_normal.method == VKEY_META.method
    assert req_normal.param["uin"] == ""
    assert req_normal.response_model is GetSongUrlsResponse

    req_encrypted = api.get_song_urls(info, file_type=EncryptedSongFileType.FLAC)
    assert req_encrypted.module == EVKEY_META.module
    assert req_encrypted.method == EVKEY_META.method

    cred = Credential(str_musicid="999999", musickey="test_key")
    req_with_ctx = SongApi(_module_client(cred)).get_song_urls(info)
    assert req_with_ctx.param["uin"] == "999999"

    too_many = [SongFileInfo(mid=f"mid_{i}") for i in range(101)]
    with pytest.raises(ValueError, match="不能超过 100"):
        api.get_song_urls(too_many)


def test_quick_search_and_search_by_type():
    """验证搜索请求描述符构建与参数组装."""
    api = SearchApi(_module_client())
    quick_req = api.quick_search("晴天")
    assert isinstance(quick_req, HttpRequest)
    assert quick_req.url == "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
    assert quick_req.params == {"key": "晴天"}
    assert quick_req.response_model is QuickSearchResponse

    type_req = api.search_by_type("周杰伦", num=20, page=2)
    assert isinstance(type_req, CgiRequest)
    assert type_req.module == "music.search.SearchCgiService"
    assert type_req.method == "DoSearchForQQMusicMobile"
    assert type_req.platform == Platform.ANDROID
    assert type_req.response_model is SearchByTypeResponse
    assert type_req.param["query"] == "周杰伦"
    assert type_req.param["num_per_page"] == 20
    assert type_req.param["page_num"] == 2
