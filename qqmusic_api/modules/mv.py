"""MV 相关 API."""

from ..utils.common import get_guid
from ._base import ApiModule


class MvApi(ApiModule):
    """MV 相关 API."""

    def get_detail(self, vids: list[str]):
        """获取 MV 详细信息.

        Args:
            vids: 视频 VID 列表.
        """
        return self._build_request(
            module="video.VideoDataServer",
            method="get_video_info_batch",
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

    def get_mv_urls(self, vids: list[str]):
        """获取 MV 播放链接.

        Args:
            vids: 视频 VID 列表.
        """
        return self._build_request(
            module="music.stream.MvUrlProxy",
            method="GetMvUrls",
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
