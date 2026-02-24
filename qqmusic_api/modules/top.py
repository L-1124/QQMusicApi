"""排行榜相关 API"""

from ..models.top import TopCategoryResponse
from ._base import ApiModule


class TopApi(ApiModule):
    """排行榜相关 API"""

    def get_category(self):
        """获取所有排行榜"""
        return self._client.build_request(
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
        tag: bool = True,
    ):
        """获取排行榜详细信息

        Args:
            top_id: 排行榜 id
            num: 返回数量
            page: 页码
            tag: 是否返回歌曲标签
        """
        return self._client.build_request(
            module="music.musicToplist.Toplist",
            method="GetDetail",
            param={
                "topId": top_id,
                "offset": num * (page - 1),
                "num": num,
                "withTags": tag,
            },
        )
