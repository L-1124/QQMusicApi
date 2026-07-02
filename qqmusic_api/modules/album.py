"""专辑相关 API."""

from typing import Any

from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter
from ..models.album import (
    AlbumFavWriteResponse,
    GetAlbumDetailResponse,
    GetAlbumSongResponse,
    GetNewAlbumResponse,
)
from ..models.request import Credential
from ._base import ApiModule


class AlbumApi(ApiModule):
    """专辑相关 API."""

    def get_detail(self, value: int | str):
        """获取专辑详细信息.

        Args:
            value: 专辑 ID 或 MID.
        """
        param: dict[str, Any] = {}
        if isinstance(value, int) or (isinstance(value, str) and value.isdecimal()):
            param["albumId"] = int(value)
        else:
            param["albumMId"] = value

        return self._build_request(
            module="music.musichallAlbum.AlbumInfoServer",
            method="GetAlbumDetail",
            param=param,
            response_model=GetAlbumDetailResponse,
        )

    def get_song(self, value: int | str, num: int = 10, page: int = 1):
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
        if isinstance(value, int) or (isinstance(value, str) and value.isdecimal()):
            param["albumId"] = int(value)
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

    def get_new_album(self, area: int = 1, num: int = 20, page: int = 1):
        """获取新碟上架列表.

        Args:
            area: 地区. 1=内地, 2=港台, 3=欧美, 4=韩国, 5=日本, 6=其他.
            num: 每页返回的专辑数量.
            page: 页码, 从 1 开始.
        """
        return self._build_request(
            module="newalbum.NewAlbumServer",
            method="get_new_album_info",
            param={"area": area, "num": num, "start": num * (page - 1)},
            response_model=GetNewAlbumResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="start", page_size_key="num"),
                adapter=ResponseAdapter(total="total", count=lambda response: len(response.albums)),
            ),
        )

    def fav_album(self, album_id: int | list[int], *, credential: Credential | None = None):
        """收藏专辑到当前登录用户.

        Args:
            album_id: 专辑 ID, 支持单个或列表.
            credential: 登录凭证.
        """
        ids = [album_id] if isinstance(album_id, int) else album_id
        return self._build_request(
            module="music.musicasset.AlbumFavWrite",
            method="FavAlbum",
            param={"v_albumId": ids},
            credential=credential,
            require_login=True,
            response_model=AlbumFavWriteResponse,
        )

    def del_fav_album(self, album_id: int | list[int], *, credential: Credential | None = None):
        """取消收藏专辑.

        Args:
            album_id: 专辑 ID, 支持单个或列表.
            credential: 登录凭证.
        """
        ids = [album_id] if isinstance(album_id, int) else album_id
        return self._build_request(
            module="music.musicasset.AlbumFavWrite",
            method="CancelFavAlbum",
            param={"v_albumId": ids},
            credential=credential,
            require_login=True,
            response_model=AlbumFavWriteResponse,
        )
