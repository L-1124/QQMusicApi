"""排行榜相关 API."""

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import OffsetStrategy
from ..models.top import TopCategoryResponse, TopDetailResponse
from ._base import ApiModule


class TopApi(ApiModule):
    """排行榜相关 API."""

    @cgi_endpoint(
        key="top.get_category",
        module="music.musicToplist.Toplist",
        method="GetAll",
        response_model=TopCategoryResponse,
    )
    def get_category(self) -> CgiRequestData:
        """获取所有排行榜分类."""
        return CgiRequestData(param={})

    @cgi_endpoint(
        key="top.get_detail",
        module="music.musicToplist.Toplist",
        method="GetDetail",
        response_model=TopDetailResponse,
    )
    def get_detail(
        self,
        top_id: int,
        num: int = 10,
        page: int = 1,
        *,
        tag: bool = True,
    ) -> CgiRequestData:
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

        return CgiRequestData(
            param=param,
            preserve_bool=tag,
            pager_strategy=OffsetStrategy[TopDetailResponse](
                offset_key="offset",
                page_size_key="num",
                total_extractor=lambda r: r.info.total_num,
                count_extractor=lambda r: len(r.songs),
            ),
            items_extractor=lambda r: r.songs,
        )
