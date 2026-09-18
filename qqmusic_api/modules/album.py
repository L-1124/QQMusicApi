"""专辑相关 API."""

from typing import Any

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import OffsetStrategy
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

    @cgi_endpoint(
        key="album.get_detail",
        module="music.musichallAlbum.AlbumInfoServer",
        method="GetAlbumDetail",
        response_model=GetAlbumDetailResponse,
    )
    def get_detail(self, value: int | str) -> CgiRequestData:
        """获取专辑详细信息.

        Args:
            value: 专辑 ID 或 MID.
        """
        param: dict[str, Any] = {}
        if isinstance(value, int) or (isinstance(value, str) and value.isdecimal()):
            param["albumId"] = int(value)
        else:
            param["albumMId"] = value

        return CgiRequestData(param=param)

    @cgi_endpoint(
        key="album.get_song",
        module="music.musichallAlbum.AlbumSongList",
        method="GetAlbumSongList",
        response_model=GetAlbumSongResponse,
    )
    def get_song(self, value: int | str, num: int = 10, page: int = 1) -> CgiRequestData:
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

        return CgiRequestData(
            param=param,
            pager_strategy=OffsetStrategy[GetAlbumSongResponse](
                offset_key="begin",
                page_size_key="num",
                total_extractor=lambda r: r.total_num,
                count_extractor=lambda r: len(r.song_list),
            ),
            items_extractor=lambda r: r.song_list,
        )

    @cgi_endpoint(
        key="album.get_new_album",
        module="newalbum.NewAlbumServer",
        method="get_new_album_info",
        response_model=GetNewAlbumResponse,
    )
    def get_new_album(self, area: int = 1, num: int = 20, page: int = 1) -> CgiRequestData:
        """获取新碟上架列表.

        Args:
            area: 地区. 1=内地, 2=港台, 3=欧美, 4=韩国, 5=日本, 6=其他.
            num: 每页返回的专辑数量.
            page: 页码, 从 1 开始.
        """
        return CgiRequestData(
            param={"area": area, "num": num, "start": num * (page - 1)},
            pager_strategy=OffsetStrategy[GetNewAlbumResponse](
                offset_key="start",
                page_size_key="num",
                total_extractor=lambda r: r.total,
                count_extractor=lambda r: len(r.albums),
            ),
            items_extractor=lambda r: r.albums,
        )

    @cgi_endpoint(
        key="album.fav_album",
        module="music.musicasset.AlbumFavWrite",
        method="FavAlbum",
        response_model=AlbumFavWriteResponse,
        require_login=True,
    )
    def fav_album(self, album_id: int | list[int], *, credential: Credential | None = None) -> CgiRequestData:
        """收藏专辑到当前登录用户.

        Args:
            album_id: 专辑 ID, 支持单个或列表.
            credential: 登录凭证.
        """
        ids = [album_id] if isinstance(album_id, int) else album_id
        return CgiRequestData(
            param={"v_albumId": ids},
            credential=credential,
        )

    @cgi_endpoint(
        key="album.del_fav_album",
        module="music.musicasset.AlbumFavWrite",
        method="CancelFavAlbum",
        response_model=AlbumFavWriteResponse,
        require_login=True,
    )
    def del_fav_album(self, album_id: int | list[int], *, credential: Credential | None = None) -> CgiRequestData:
        """取消收藏专辑.

        Args:
            album_id: 专辑 ID, 支持单个或列表.
            credential: 登录凭证.
        """
        ids = [album_id] if isinstance(album_id, int) else album_id
        return CgiRequestData(
            param={"v_albumId": ids},
            credential=credential,
        )
