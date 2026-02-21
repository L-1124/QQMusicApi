"""测试 API 模块基类及挂载属性"""

from qqmusic_api.core.client import Client
from qqmusic_api.modules._base import ApiModule


def test_api_module_base() -> None:
    """测试 ApiModule 基类初始化。"""
    client = Client()
    module = ApiModule(client)
    assert module._client is client


def test_client_properties() -> None:
    """测试 Client 模块属性挂载及 using() 安全性。"""
    client = Client()

    # 验证各模块属性存在并返回 ApiModule (或其子类) 实例
    assert isinstance(client.comment, ApiModule)
    assert isinstance(client.recommend, ApiModule)
    assert isinstance(client.top, ApiModule)
    assert isinstance(client.album, ApiModule)
    assert isinstance(client.mv, ApiModule)

    # 验证每次调用返回新实例 (不使用缓存)
    assert client.comment is not client.comment

    # 验证 using() 后的 client 引用正确
    new_client = client.using(client.credential)
    assert new_client is not client
    assert new_client.comment._client is new_client
    assert client.comment._client is client


def test_client_build_result_struct() -> None:
    """测试 Client._build_result 处理 TarsDict 转换。"""
    from tarsio import Struct, TarsDict, field

    from qqmusic_api.core.client import Client

    class MyStruct(Struct):
        id: int = field(tag=0)
        name: str = field(tag=1)

    raw_data = TarsDict({0: 123, 1: "test"})
    result = Client._build_result(raw_data, MyStruct)
    assert isinstance(result, MyStruct)
    assert result.id == 123
    assert result.name == "test"
