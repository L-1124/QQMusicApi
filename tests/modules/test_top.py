"""TopApi 测试."""

import pytest

from qqmusic_api.models.top import TopCategoryResponse
from qqmusic_api.modules.top import TopApi


@pytest.fixture
def top_api(mock_client):
    """TopApi 实例."""
    return TopApi(mock_client)


@pytest.mark.anyio
async def test_get_category(top_api, mock_client):
    """测试获取排行榜分类."""
    mock_client.execute.return_value = TopCategoryResponse(group=[])

    # 构建请求
    request = top_api.get_category()
    result = await mock_client.execute(request)

    assert isinstance(result, TopCategoryResponse)
    assert request.module == "music.musicToplist.Toplist"
    assert request.method == "GetAll"
    assert request.param == {}
    assert request.response_model == TopCategoryResponse


@pytest.mark.anyio
async def test_get_detail(top_api, mock_client):
    """测试获取排行榜详情."""
    mock_client.execute.return_value = {"topId": 4}

    # 构建请求
    request = top_api.get_detail(top_id=4, num=20, page=2, tag=False)
    result = await mock_client.execute(request)

    assert result == {"topId": 4}
    assert request.module == "music.musicToplist.Toplist"
    assert request.method == "GetDetail"
    assert request.param == {
        "topId": 4,
        "offset": 20,
        "num": 20,
        "withTags": False,
    }
    assert request.response_model is None
