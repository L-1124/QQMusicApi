"""MV 相关 API"""

import random
from typing import Any

from .utils.common import get_guid
from .utils.network import NO_PROCESSOR, api_request


@api_request("video.VideoDataServer", "get_video_info_batch")
async def get_detail(vids: list[str]):
    """获取 MV 详细信息

    Args:
        vids: 视频 vid 列表
    """
    return {
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
    }, NO_PROCESSOR


@api_request("music.stream.MvUrlProxy", "GetMvUrls")
async def get_mv_urls(vids: list[str]):
    """获取 MV 播放链接

    Args:
        vids: 视频 vid 列表
    """

    def get_play_urls(data):
        play_urls = {}
        for url_info in data:
            if url_info["freeflow_url"]:
                play_url = random.choice(url_info["freeflow_url"])
                play_urls[url_info["filetype"]] = play_url
        return play_urls

    def _processor(data: dict[str, Any]):
        urls: dict[str, dict] = {}
        for _, data in data.items():
            urls[_] = {}
            urls[_]["mp4"] = get_play_urls(data["mp4"])
            urls[_]["hls"] = get_play_urls(data["hls"])
        return urls

    return {
        "vids": vids,
        "request_type": 10003,
        "guid": get_guid(),
        "videoformat": 1,
        "format": 265,
        "dolby": 1,
        "use_new_domain": 1,
        "use_ipv6": 1,
    }, _processor
