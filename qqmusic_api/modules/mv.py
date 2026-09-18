"""MV 相关 API."""

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import OffsetStrategy
from ..models.mv import GetMvDetailResponse, GetMvListResponse, GetMvUrlsResponse, MvListItem
from ..utils.common import get_guid
from ._base import ApiModule


class MvApi(ApiModule):
    """MV 相关 API."""

    @cgi_endpoint(
        key="mv.get_detail",
        module="video.VideoDataServer",
        method="get_video_info_batch",
        response_model=GetMvDetailResponse,
    )
    def get_detail(self, vids: list[str]) -> CgiRequestData:
        """获取 MV 详细信息.

        Args:
            vids: 视频 VID 列表.
        """
        return CgiRequestData(
            param={
                "vidlist": vids,
                "required": [
                    "vid",
                    "type",
                    "sid",
                    "cover_pic",
                    "duration",
                    "singers",
                    "video_switch",
                    "msg",
                    "name",
                    "desc",
                    "playcnt",
                    "pubdate",
                    "isfav",
                    "gmid",
                    "uploader_headurl",
                    "uploader_nick",
                    "uploader_encuin",
                    "uploader_uin",
                    "uploader_hasfollow",
                    "uploader_follower_num",
                    "uploader_hasfollow",
                    "related_songs",
                ],
            },
        )

    @cgi_endpoint(
        key="mv.get_mv_urls",
        module="music.stream.MvUrlProxy",
        method="GetMvUrls",
        response_model=GetMvUrlsResponse,
    )
    def get_mv_urls(self, vids: list[str]) -> CgiRequestData:
        """获取 MV 播放链接.

        Args:
            vids: 视频 VID 列表.
        """
        return CgiRequestData(
            param={
                "vids": vids,
                "request_type": 10003,
                "guid": get_guid(),
                "videoformat": 1,
                "format": 265,
                "dolby": 1,
                "use_new_domain": 1,
                "use_ipv6": 1,
            },
        )

    @cgi_endpoint(
        key="mv.get_mv_list",
        module="MvService.MvInfoProServer",
        method="GetAllocMvInfo",
        response_model=GetMvListResponse,
        item_type=MvListItem,
    )
    def get_mv_list(
        self,
        area: int = 15,
        version: int = 7,
        order: int = 0,
        num: int = 10,
        page: int = 1,
    ) -> CgiRequestData:
        """获取 MV 分类列表.

        Args:
            area: 地区 ID. 15=全部, 8=内地, 5=港台, 6=欧美, 7=韩国, 4=日本.
            version: 类型 ID. 7=全部, 8=MV, 13=现场, 14=翻唱, 15=舞蹈, 16=影视, 17=综艺, 18=儿歌.
            order: 排序方式. 0=最新, 1=最热.
            num: 每页返回数量.
            page: 页码, 从 1 开始.
        """
        return CgiRequestData(
            param={"area": area, "version": version, "order": order, "start": num * (page - 1), "size": num},
            pager_strategy=OffsetStrategy[GetMvListResponse](
                offset_key="start",
                page_size_key="size",
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.items),
            ),
            items_extractor=lambda r: r.items,
        )
