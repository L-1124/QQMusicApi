"""歌曲相关 API 模块."""

from enum import Enum
from typing import Any

from qqmusic_api import Platform

from ..core.pagination import BatchRefreshStrategy, RefreshMeta, ResponseAdapter
from ..models.request import Credential
from ..models.song import (
    GetCdnDispatchResponse,
    GetFavNumResponse,
    GetOtherVersionResponse,
    GetProducerResponse,
    GetRelatedMvResponse,
    GetRelatedSonglistResponse,
    GetSheetResponse,
    GetSimilarSongResponse,
    GetSongDetailResponse,
    GetSongLabelsResponse,
    GetSongUrlsResponse,
    QuerySongResponse,
)
from ..utils import get_guid
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
    """普通歌曲文件类型.

    + DTS_X: DTS:X,size_new[9]
    + MASTER: 臻品母带,size_new[0]
    + ATMOS_2: 臻品音质,size_new[1]
    + ATMOS_51: 臻品全景声 5.1,size_new[2]
    + ATMOS_71: 臻品全景声 7.1,size_new[6]
    + ATMOS_DB: 杜比全景声,size_dolby
    + NAC: 腾讯自研 AICodec,size_new[7]
    + FLAC: SQ 无损音质,size_flac
    + OGG_640: SQ 无损,size_new[5]
    + OGG_320: HQ 高品质(OGG),size_new[3]
    + OGG_192: HQ 高品质(OGG),size_192ogg
    + OGG_96: 流畅音质(OGG),size_96ogg
    + MP3_320: HQ 高品质,size_320mp3
    + MP3_128: 标准音质,size_128mp3
    + ACC_192: HQ 高品质(AAC),size_192aac
    + ACC_96: 流畅音质,size_96aac
    + ACC_48: 低品质,size_48aac
    """

    DTS_X = ("DT03", ".mp4")
    MASTER = ("AI00", ".flac")
    ATMOS_2 = ("Q000", ".flac")
    ATMOS_51 = ("Q001", ".flac")
    ATMOS_71 = ("Q003", ".ogg")
    ATMOS_DB = ("D004", ".mp4")
    NAC = ("TL01", ".nac")
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
    """加密歌曲文件类型.

    + DTS_X: DTS:X,size_new[9]
    + VINYL: 黑胶,size_new[4]
    + MASTER: 臻品母带,size_new[0]
    + ATMOS_2: 臻品音质,size_new[1]
    + ATMOS_51: 臻品全景声 5.1,size_new[2]
    + ATMOS_71: 臻品全景声 7.1,size_new[6]
    + ATMOS_DB: 杜比全景声,size_dolby
    + NAC: 腾讯自研 AICodec
    + FLAC: SQ 无损音质,size_flac
    + OGG_640: SQ 无损,size_new[5]
    + OGG_320: HQ 高品质(OGG),size_new[3]
    + OGG_192: HQ 高品质(OGG),size_192ogg
    + OGG_96: 流畅音质(OGG),size_96ogg
    """

    DTS_X = ("DTM3", ".mmp4")
    VINYL = ("V0M0", ".mflac")
    MASTER = ("AIM0", ".mflac")
    ATMOS_2 = ("Q0M0", ".mflac")
    ATMOS_51 = ("Q0M1", ".mflac")
    ATMOS_71 = ("Q0M3", ".mgg")
    ATMOS_DB = ("D0M4", ".mmp4")
    NAC = ("TLM1", ".mnac")
    FLAC = ("F0M0", ".mflac")
    OGG_640 = ("O8M1", ".mgg")
    OGG_320 = ("O8M0", ".mgg")
    OGG_192 = ("O6M0", ".mgg")
    OGG_96 = ("O4M0", ".mgg")


class SongApi(ApiModule):
    """歌曲相关 API 模块类."""

    _GET_SONG_URLS_MAX_MID = 100
    _SONG_URL_FALLBACK_DOMAIN = "https://isure.stream.qqmusic.qq.com/"

    def __init__(self, client) -> None:
        """初始化歌曲模块."""
        super().__init__(client)
        self._SONG_URL_DOMAINS: tuple[str, ...] = ()
        self._song_url_dispatch_data: dict[str, Any] | None = None
        self._song_url_dispatch_refresh_at = 0.0
        self._song_url_dispatch_expire_at = 0.0
        self._song_url_domain_infos: dict[str, dict[str, Any]] = {}

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
        return self._build_request(
            module="music.trackInfo.UniformRuleCtrl",
            method="CgiGetTrackInfo",
            param=params,
            response_model=QuerySongResponse,
        )

    def get_cdn_dispatch(
        self,
        *,
        use_new_domain: bool = True,
        use_ipv6: bool = True,
    ):
        """获取并缓存音频 CDN 调度信息.

        Args:
            use_new_domain: 是否启用新域名.
            use_ipv6: 是否启用 IPv6.
        """
        return self._build_request(
            module="music.audioCdnDispatch.cdnDispatch",
            method="GetCdnDispatch",
            param={
                "guid": get_guid(),
                "uid": "0",
                "use_new_domain": int(use_new_domain),
                "use_ipv6": int(use_ipv6),
            },
            response_model=GetCdnDispatchResponse,
        )

    def get_song_urls(
        self,
        mid: list[str],
        file_type: SongFileType | EncryptedSongFileType = SongFileType.MP3_128,
        credential: Credential | None = None,
        *,
        media_mid: list[str] | None = None,
    ):
        """获取歌曲文件链接.

        Args:
            mid: 歌曲 MID 列表.
            file_type: 歌曲文件类型.
            credential: 凭据对象.
            media_mid: 获取媒体文件链接时需要的 media_mid 列表,与 mid 一一对应.

        Raises:
            ValueError: 当 `mid` 数量超过上限时抛出.
        """
        if len(mid) > self._GET_SONG_URLS_MAX_MID:
            raise ValueError(f"mid 数量不能超过 {self._GET_SONG_URLS_MAX_MID}, 当前为 {len(mid)}")
        if media_mid and len(media_mid) != len(mid):
            raise ValueError("media_mid 必须与 mid 一一对应")
        encrypted = isinstance(file_type, EncryptedSongFileType)
        module, method = (
            ("music.vkey.GetVkey", "UrlGetVkey") if not encrypted else ("music.vkey.GetEVkey", "CgiGetEVkey")
        )
        filename = (
            [f"{file_type.s}{item}{item}{file_type.e}" for item in mid]
            if not media_mid
            else [f"{file_type.s}{m}{file_type.e}" for m in media_mid]
        )

        return self._build_request(
            module=module,
            method=method,
            param={
                "uin": self._client.credential.str_musicid if not credential else credential.str_musicid,
                "filename": filename,
                "guid": get_guid(),
                "songmid": mid,
                "songtype": [0] * len(mid),
                "ctx": 0,
            },
            response_model=GetSongUrlsResponse,
        )

    def get_detail(self, value: str | int):
        """获取歌曲详细信息.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = {"song_id": value} if isinstance(value, int) else {"song_mid": value}
        return self._build_request(
            module="music.pf_song_detail_svr",
            method="get_song_detail_yqq",
            param=param,
            platform=Platform.WEB,
            response_model=GetSongDetailResponse,
        )

    def get_similar_song(self, songid: int):
        """获取相似歌曲.

        Args:
            songid: 歌曲 ID.
        """
        return self._build_request(
            module="music.recommend.TrackRelationServer",
            method="GetSimilarSongs",
            param={"songid": songid},
            response_model=GetSimilarSongResponse,
        )

    def get_lables(self, songid: int):
        """获取歌曲标签.

        Args:
            songid: 歌曲 ID.
        """
        return self._build_request(
            module="music.recommend.TrackRelationServer",
            method="GetSongLabels",
            param={"songid": songid},
            response_model=GetSongLabelsResponse,
        )

    def get_related_songlist(self, songid: int, last: list[int] | None = None):
        """获取歌曲相关歌单.

        Args:
            songid: 歌曲 ID.
            last: 上次请求的相关歌单 ID 列表, 用于换一批歌单.
        """
        return self._build_request(
            module="music.recommend.TrackRelationServer",
            method="GetRelatedPlaylist",
            param={"songid": songid, "vecPlaylist": last or []},
            response_model=GetRelatedSonglistResponse,
            refresh_meta=RefreshMeta(
                strategy=BatchRefreshStrategy(refresh_key="vecPlaylist"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    cursor=lambda response: (
                        [playlist.id for playlist in response.songlist] if response.songlist else None
                    ),
                ),
            ),
        )

    def get_related_mv(self, songid: int, last_mvid: str | None = None):
        """获取歌曲相关 MV.

        Args:
            songid: 歌曲 ID.
            last_mvid: 上一个 MV 的 VID (可选).
        """
        return self._build_request(
            module="MvService.MvInfoProServer",
            method="GetSongRelatedMv",
            param={"songid": str(songid), "songtype": 1, "lastmvid": last_mvid or 0},
            response_model=GetRelatedMvResponse,
            refresh_meta=RefreshMeta(
                strategy=BatchRefreshStrategy(refresh_key="lastmvid"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    cursor=lambda response: response.mv[-1].id if response.mv else None,
                ),
            ),
        )

    def get_other_version(self, value: str | int):
        """获取歌曲其他版本.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = {"songid": value} if isinstance(value, int) else {"songmid": value}
        return self._build_request(
            module="music.musichallSong.OtherVersionServer",
            method="GetOtherVersionSongs",
            param=param,
            response_model=GetOtherVersionResponse,
        )

    def get_producer(self, value: str | int):
        """获取歌曲制作人信息.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = {"songid": value} if isinstance(value, int) else {"songmid": value}
        return self._build_request(
            module="music.sociality.KolWorksTag",
            method="SongProducer",
            param=param,
            response_model=GetProducerResponse,
        )

    def get_sheet(self, mid: str):
        """获取歌曲相关曲谱.

        Args:
            mid: 歌曲 MID.
        """
        return self._build_request(
            module="music.mir.SheetMusicSvr",
            method="GetMoreSheetMusic",
            param={"songmid": mid, "scoreType": -1},
            response_model=GetSheetResponse,
        )

    def get_fav_num(self, song_ids: list[int]):
        """获取歌曲收藏数量原始数据.

        Args:
            song_ids: 歌曲 ID 列表.
        """
        return self._build_request(
            module="music.musicasset.SongFavRead",
            method="GetSongFansNumberById",
            param={"v_songId": song_ids},
            response_model=GetFavNumResponse,
        )
