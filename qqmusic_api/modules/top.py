"""排行榜相关 API."""

from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter
from ..models.top import TopCategoryResponse, TopDetailResponse
from ._base import ApiModule


class TopApi(ApiModule):
    """排行榜相关 API."""

    def get_category(self):
        """获取所有排行榜分类."""
        return self._build_request(
            module="music.musicToplist.Toplist",
            method="GetAll",
            param={},
            response_model=TopCategoryResponse,
        )

    def get_detail(
        self,
        top_id: int,
        num: int = 10,
        page: int = 1,
        *,
        tag: bool = True,
    ):
        """获取排行榜详情及其歌曲列表.

        Args:
            top_id: 排行榜 ID.
            num: 返回歌曲数量.
            page: 页码.
            tag: 是否返回歌曲标签信息.
        """
        param = {
            "topId": top_id,
            "offset": num * (page - 1),
            "num": num,
        }
        if tag:
            param["withTags"] = True

        return self._build_request(
            module="music.musicToplist.Toplist",
            method="GetDetail",
            param=param,
            preserve_bool=tag,
            response_model=TopDetailResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="offset", page_size_key="num"),
                adapter=ResponseAdapter(
                    total=lambda response: response.info.total_num,
                    count=lambda response: len(response.songs),
                ),
            ),
        )
