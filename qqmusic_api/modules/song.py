"""歌曲相关 API 模块."""

from enum import Enum
from typing import Any

from ..utils.common import get_guid
from ._base import ApiModule


class BaseSongFileType(Enum):
    """基础歌曲文件类型枚举类."""

    def __init__(self, start_code: str, extension: str) -> None:
        """初始化歌曲文件类型.

        Args:
            start_code: 歌曲文件编码前缀.
            extension: 歌曲文件后缀.
        """
        self._start_code = start_code
        self._extension = extension

    @property
    def s(self) -> str:
        """歌曲文件编码前缀."""
        return self._start_code

    @property
    def e(self) -> str:
        """歌曲文件后缀."""
        return self._extension


class SongFileType(BaseSongFileType):
    """普通歌曲文件类型."""

    MASTER = ("AI00", ".flac")
    ATMOS_2 = ("Q000", ".flac")
    ATMOS_51 = ("Q001", ".flac")
    FLAC = ("F000", ".flac")
    OGG_640 = ("O801", ".ogg")
    OGG_320 = ("O800", ".ogg")
    OGG_192 = ("O600", ".ogg")
    OGG_96 = ("O400", ".ogg")
    MP3_320 = ("M800", ".mp3")
    MP3_128 = ("M500", ".mp3")
    ACC_192 = ("C600", ".m4a")
    ACC_96 = ("C400", ".m4a")
    ACC_48 = ("C200", ".m4a")


class EncryptedSongFileType(BaseSongFileType):
    """加密歌曲文件类型."""

    MASTER = ("AIM0", ".mflac")
    ATMOS_2 = ("Q0M0", ".mflac")
    ATMOS_51 = ("Q0M1", ".mflac")
    FLAC = ("F0M0", ".mflac")
    OGG_640 = ("O801", ".mgg")
    OGG_320 = ("O800", ".mgg")
    OGG_192 = ("O6M0", ".mgg")
    OGG_96 = ("O4M0", ".mgg")


class SongApi(ApiModule):
    """歌曲相关 API 模块类."""

    def query_song(self, value: list[int] | list[str]):
        """根据 id 或 mid 获取歌曲信息.

        Args:
            value: 歌曲 ID 列表或 MID 列表.

        Raises:
            ValueError: 如果 `value` 为空.
        """
        if not value:
            raise ValueError("value 不能为空")
        params: dict[str, Any] = {
            "types": [0 for _ in range(len(value))],
            "modify_stamp": [0 for _ in range(len(value))],
            "ctx": 0,
            "client": 1,
        }
        if isinstance(value[0], int):
            params["ids"] = value
        else:
            params["mids"] = value
        return self.build_request(
            module="music.trackInfo.UniformRuleCtrl",
            method="CgiGetTrackInfo",
            param=params,
        )

    def get_try_url(self, mid: str, vs: str):
        """获取试听文件链接原始数据.

        Args:
            mid: 歌曲 MID.
            vs: 歌曲 vs 标识.
        """
        return self.build_request(
            module="music.vkey.GetVkey",
            method="UrlGetVkey",
            param={
                "filename": [f"RS02{vs}.mp3"],
                "guid": get_guid(),
                "songmid": [mid],
                "songtype": [1],
            },
        )

    def get_detail(self, value: str | int):
        """获取歌曲详细信息.

        Args:
            value: 歌曲 ID 或 MID.
        """
        if isinstance(value, int):
            param = {"song_id": value}
        else:
            param = {"song_mid": value}
        return self.build_request(
            module="music.pf_song_detail_svr",
            method="get_song_detail_yqq",
            param=param,
        )

    def get_similar_song(self, songid: int):
        """获取相似歌曲.

        Args:
            songid: 歌曲 ID.
        """
        return self.build_request(
            module="music.recommend.TrackRelationServer",
            method="GetSimilarSongs",
            param={"songid": songid},
        )

    def get_lables(self, songid: int):
        """获取歌曲标签.

        Args:
            songid: 歌曲 ID.
        """
        return self.build_request(
            module="music.recommend.TrackRelationServer",
            method="GetSongLabels",
            param={"songid": songid},
        )

    def get_related_songlist(self, songid: int):
        """获取歌曲相关歌单.

        Args:
            songid: 歌曲 ID.
        """
        return self.build_request(
            module="music.recommend.TrackRelationServer",
            method="GetRelatedPlaylist",
            param={"songid": songid},
        )

    def get_related_mv(self, songid: int, last_mvid: str | None = None):
        """获取歌曲相关 MV.

        Args:
            songid: 歌曲 ID.
            last_mvid: 上一个 MV 的 VID (可选).
        """
        params: dict[str, Any] = {"songid": songid, "songtype": 1}
        if last_mvid:
            params["lastmvid"] = last_mvid
        return self.build_request(
            module="MvService.MvInfoProServer",
            method="GetSongRelatedMv",
            param=params,
        )

    def get_other_version(self, value: str | int):
        """获取歌曲其他版本.

        Args:
            value: 歌曲 ID 或 MID.
        """
        if isinstance(value, int):
            param = {"songid": value}
        else:
            param = {"songmid": value}
        return self.build_request(
            module="music.musichallSong.OtherVersionServer",
            method="GetOtherVersionSongs",
            param=param,
        )

    def get_producer(self, value: str | int):
        """获取歌曲制作人信息.

        Args:
            value: 歌曲 ID 或 MID.
        """
        if isinstance(value, int):
            param = {"songid": value}
        else:
            param = {"songmid": value}
        return self.build_request(
            module="music.sociality.KolWorksTag",
            method="SongProducer",
            param=param,
        )

    def get_sheet(self, mid: str):
        """获取歌曲相关曲谱.

        Args:
            mid: 歌曲 MID.
        """
        return self.build_request(
            module="music.mir.SheetMusicSvr",
            method="GetMoreSheetMusic",
            param={"songmid": mid, "scoreType": -1},
        )

    def get_fav_num(self, songid: list[int]):
        """获取歌曲收藏数量原始数据.

        Args:
            songid: 歌曲 ID 列表.
        """
        return self.build_request(
            module="music.musicasset.SongFavRead",
            method="GetSongFansNumberById",
            param={"v_songId": songid},
        )
