"""专辑相关 API."""

from typing import Any, Literal

from ._base import ApiModule


class AlbumApi(ApiModule):
    """专辑相关 API."""

    def get_cover(self, mid: str, size: Literal[150, 300, 500, 800] = 300) -> str:
        """获取专辑封面链接.

        Args:
            mid: 专辑 MID.
            size: 封面大小, 支持 150, 300, 500, 800.

        Returns:
            str: 封面图片 URL 地址.
        """
        if size not in [150, 300, 500, 800]:
            raise ValueError("not supported size")
        return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{mid}.jpg"

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
        )
