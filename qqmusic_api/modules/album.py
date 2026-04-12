"""专辑相关 API."""

from typing import Any

from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter
from ..models.album import GetAlbumDetailResponse, GetAlbumSongResponse
from ._base import ApiModule


class AlbumApi(ApiModule):
    """专辑相关 API."""

    def get_detail(self, value: str | int):
        """获取专辑详细信息.

        Args:
            value: 专辑 ID 或 MID.
        """
        param: dict[str, Any] = {}
        if isinstance(value, int):
            param["albumId"] = value
        else:
            param["albumMId"] = value

        return self._build_request(
            module="music.musichallAlbum.AlbumInfoServer",
            method="GetAlbumDetail",
            param=param,
            response_model=GetAlbumDetailResponse,
        )

    def get_song(self, value: str | int, num: int = 10, page: int = 1):
        """获取专辑歌曲列表.

        Args:
            value: 专辑 ID 或 MID.
            num: 返回结果数量.
            page: 页码.
        """
        param: dict[str, Any] = {
            "begin": num * (page - 1),
            "num": num,
        }
        if isinstance(value, int):
            param["albumId"] = value
        else:
            param["albumMid"] = value

        return self._build_request(
            module="music.musichallAlbum.AlbumSongList",
            method="GetAlbumSongList",
            param=param,
            response_model=GetAlbumSongResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="begin", page_size_key="num"),
                adapter=ResponseAdapter(total="total_num", count=lambda response: len(response.song_list)),
            ),
        )
