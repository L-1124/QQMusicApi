"""歌曲相关 API 模块."""

from enum import Enum
from typing import Any, NamedTuple

from qqmusic_api import Platform

from ..core.pagination import BatchRefreshStrategy
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
    HasSheetMusicResponse,
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


class SpecialSongFileType(BaseSongFileType):
    """特殊歌曲文件类型.

    + TRY: 歌曲试听. vs[0].
    + TRY_OGG_640: SQ 无损试听,size_new[5]
    + ACCOM: 纯人声/伴奏轨道. vs[9].
    + MULTI: 多轨文件. vs[18].
    + PIANO: AI演奏-钢琴. vs[13].
    + BAYIN: AI演奏-八音盒. vs[17].
    + GUZHENG: AI演奏-古筝. vs[14].
    + QUDI: AI演奏-曲笛. vs[16].
    + HULUSI: AI演奏-葫芦丝. vs[15].
    + SUONA: AI演奏-唢呐. vs[19].
    + SHOUDIE: AI演奏-手碟. vs[20].
    + GUITAR: AI演奏-电吉他. vs[21].
    + DRUMS: AI演奏-架子鼓. vs[22].
    + KAZOO: AI演奏-卡祖笛. vs[26].
    + THERAPY: AI疗愈音效. vs[27].
    """

    TRY = ("RS02", ".mp3")
    TRY_OGG_640 = ("O802", ".ogg")
    ACCOM = ("O801", ".ogg")
    MULTI = ("O601", ".ogg")
    PIANO = ("AI01", ".ogg")
    BAYIN = ("AI02", ".ogg")
    GUZHENG = ("AI03", ".ogg")
    QUDI = ("AI04", ".ogg")
    HULUSI = ("AI05", ".ogg")
    SUONA = ("AI06", ".ogg")
    SHOUDIE = ("AI07", ".ogg")
    GUITAR = ("AI08", ".ogg")
    DRUMS = ("AI09", ".ogg")
    KAZOO = ("A200", ".ogg")
    THERAPY = ("AA01", ".ogg")


class RingSongFileType(BaseSongFileType):
    """彩铃文件类型.

    + RING_128: 高品质彩铃 (128k)
    + RING_96: 标准彩铃 (96k)
    + RING_48: 低品质彩铃 (48k)
    """

    RING_128 = ("R500", ".mp3")
    RING_96 = ("R400", ".m4a")
    RING_48 = ("R200", ".m4a")


class SongFileInfo(NamedTuple):
    """歌曲文件信息.

    Attributes:
        mid: 歌曲 MID.
        file_type: 歌曲文件类型.
        song_type: 歌曲类型.
        media_mid: 媒体文件 mid.
    """

    mid: str
    file_type: BaseSongFileType | None = None
    song_type: int | None = None
    media_mid: str | None = None


class SongQueryInfo(NamedTuple):
    """歌曲查询信息.

    Attributes:
        id: 歌曲 ID.
        mid: 歌曲 MID.
        song_type: 歌曲类型.
    """

    id: int | None = None
    mid: str | None = None
    song_type: int | None = None


class SongApi(ApiModule):
    """歌曲相关 API 模块类."""

    _GET_SONG_URLS_MAX_MID = 100
    _SONG_URL_FALLBACK_DOMAIN = "https://isure.stream.qqmusic.qq.com/"

    def query_song(
        self,
        song_info: list[SongQueryInfo],
    ):
        """批量获取歌曲信息.

        Args:
            song_info: SongQueryInfo 列表.

        Raises:
            ValueError: 如果 `song_info` 为空, 或参数不匹配.
        """
        if not song_info:
            raise ValueError("song_info 不能为空")

        ids, mids, types = [], [], []
        for item in song_info:
            if (item.id is None) == (item.mid is None):
                raise ValueError("SongQueryInfo 必须提供 id 或 mid 且不能同时提供")

            if item.id is not None:
                ids.append(item.id)
            else:
                mids.append(item.mid)
            types.append(item.song_type or 0)

        params: dict[str, Any] = {
            "ctx": 0,
            "client": 1,
            "types": types,
            "modify_stamp": [0] * len(types),
        }

        if ids:
            params["ids"] = ids
        if mids:
            params["mids"] = mids

        return self._build_cgi(
            module="music.trackInfo.UniformRuleCtrl",
            method="CgiGetTrackInfo",
            param=params,
            response_model=QuerySongResponse,
        )

    def get_cdn_dispatch(self):
        """获取音频链接 CDN 信息."""
        return self._build_cgi(
            module="music.audioCdnDispatch.cdnDispatch",
            method="GetCdnDispatch",
            param={
                "guid": get_guid(),
                "uid": "0",
                "use_new_domain": 1,
                "use_ipv6": 1,
            },
            response_model=GetCdnDispatchResponse,
        )

    def get_song_urls(
        self,
        file_info: list[SongFileInfo],
        file_type: BaseSongFileType = SongFileType.MP3_128,
        credential: Credential | None = None,
    ):
        """获取歌曲文件链接.

        Args:
            file_info: 歌曲文件信息列表.
            file_type: 歌曲文件类型.
            credential: 凭据对象.

        Raises:
            ValueError: 当 `mid` 数量超过上限时抛出. 超限时上游返回错误且无结果, 故提前拒绝.
        """
        if len(file_info) > self._GET_SONG_URLS_MAX_MID:
            raise ValueError(f"mid 数量不能超过 {self._GET_SONG_URLS_MAX_MID}, 当前为 {len(file_info)}")

        encrypted = isinstance(file_type, EncryptedSongFileType)
        module, method = (
            ("music.vkey.GetVkey", "UrlGetVkey") if not encrypted else ("music.vkey.GetEVkey", "CgiGetEVkey")
        )
        songmid: list[str] = []
        filename: list[str] = []
        songtype: list[int] = []
        for item in file_info:
            songmid.append(item.mid)
            final_file_type = item.file_type or file_type

            filename.append(
                f"{final_file_type.s}{item.mid}{item.mid}{final_file_type.e}"
                if not item.media_mid
                else f"{final_file_type.s}{item.media_mid}{final_file_type.e}",
            )
            songtype.append(item.song_type or 0)

        return self._build_cgi(
            module=module,
            method=method,
            param={
                "uin": self._client.credential.str_musicid if not credential else credential.str_musicid,
                "filename": filename,
                "guid": get_guid(),
                "songmid": songmid,
                "songtype": songtype,
                "ctx": 0,
            },
            response_model=GetSongUrlsResponse,
            credential=credential,
        )

    def get_detail(self, value: int | str):
        """获取歌曲详细信息.

        固定使用 Web 平台.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = (
            {"song_id": int(value)}
            if isinstance(value, int) or (isinstance(value, str) and value.isdecimal())
            else {"song_mid": value}
        )
        return self._build_cgi(
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
        return self._build_cgi(
            module="music.recommend.TrackRelationServer",
            method="GetSimilarSongs",
            param={"songid": songid},
            response_model=GetSimilarSongResponse,
        )

    def get_labels(self, songid: int):
        """获取歌曲标签.

        Args:
            songid: 歌曲 ID.
        """
        return self._build_cgi(
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
        return self._build_cgi(
            module="music.recommend.TrackRelationServer",
            method="GetRelatedPlaylist",
            param={"songid": songid, "vecPlaylist": last or []},
            response_model=GetRelatedSonglistResponse,
            pager_strategy=BatchRefreshStrategy[GetRelatedSonglistResponse](
                refresh_key="vecPlaylist",
                has_more_extractor=lambda r: bool(r.has_more),
                cursor_extractor=lambda r: [playlist.id for playlist in r.songlist] if r.songlist else None,
            ),
        ).with_extractor(lambda r: r.songlist)

    def get_related_mv(self, songid: int, last_mvid: str | None = None):
        """获取歌曲相关 MV.

        Args:
            songid: 歌曲 ID.
            last_mvid: 上一个 MV 的 VID (可选).
        """
        return self._build_cgi(
            module="MvService.MvInfoProServer",
            method="GetSongRelatedMv",
            param={"songid": str(songid), "songtype": 1, "lastmvid": last_mvid or 0},
            response_model=GetRelatedMvResponse,
            pager_strategy=BatchRefreshStrategy[GetRelatedMvResponse](
                refresh_key="lastmvid",
                has_more_extractor=lambda r: bool(r.has_more),
                cursor_extractor=lambda r: r.mv[-1].id if r.mv else None,
            ),
        ).with_extractor(lambda r: r.mv)

    def get_other_version(self, value: int | str):
        """获取歌曲其他版本.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = (
            {"songid": int(value)}
            if isinstance(value, int) or (isinstance(value, str) and value.isdecimal())
            else {"songmid": value}
        )
        return self._build_cgi(
            module="music.musichallSong.OtherVersionServer",
            method="GetOtherVersionSongs",
            param=param,
            response_model=GetOtherVersionResponse,
        )

    def get_producer(self, value: int | str):
        """获取歌曲制作人信息.

        Args:
            value: 歌曲 ID 或 MID.
        """
        param = (
            {"songid": int(value)}
            if isinstance(value, int) or (isinstance(value, str) and value.isdecimal())
            else {"songmid": value}
        )
        return self._build_cgi(
            module="music.sociality.KolWorksTag",
            method="SongProducer",
            param=param,
            response_model=GetProducerResponse,
        )

    def get_sheet(self, mid: str, ttype: int = 0):
        """获取歌曲相关曲谱.

        Args:
            mid: 歌曲 MID.
            ttype: 曲谱来源类型. 0=用户上传, 1=引擎/AI曲谱, 2=虫虫钢琴.
        """
        if ttype == 2:
            return self._build_cgi(
                module="music.mir.SheetMusicSvr",
                method="GetChongChongSheetMusic",
                param={"songMid": mid, "begin": 0, "end": 100, "scoreType": -1, "ttype": 1},
                response_model=GetSheetResponse,
                comm={
                    "g_tk": 5381,
                    "uin": "",
                    "format": "json",
                    "inCharset": "utf-8",
                    "outCharset": "utf-8",
                    "notice": 0,
                    "platform": "h5",
                    "needNewCode": 1,
                },
                sign=True,
                override_comm=True,
                allow_error_codes={10007},
                parse_on_allow=True,
            )
        score_type = -473 if ttype == 1 else -1
        return self._build_cgi(
            module="music.mir.SheetMusicSvr",
            method="GetMoreSheetMusic",
            param={"songMid": mid, "begin": 0, "end": 100, "scoreType": score_type, "ttype": ttype},
            response_model=GetSheetResponse,
            comm={
                "g_tk": 5381,
                "uin": "",
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "needNewCode": 1,
            },
            override_comm=True,
            allow_error_codes={10007},
            parse_on_allow=True,
        )

    def has_sheet(self, mid: str):
        """检查歌曲是否有曲谱.

        Args:
            mid: 歌曲 MID.
        """
        return self._build_cgi(
            module="music.mir.SheetMusicSvr",
            method="HasSheetMusic",
            param={"songMid": mid},
            response_model=HasSheetMusicResponse,
            comm={
                "g_tk": 5381,
                "uin": "",
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "needNewCode": 1,
            },
            override_comm=True,
        )

    def get_fav_num(self, song_ids: list[int]):
        """获取歌曲收藏数量原始数据.

        Args:
            song_ids: 歌曲 ID 列表.
        """
        return self._build_cgi(
            module="music.musicasset.SongFavRead",
            method="GetSongFansNumberById",
            param={"v_songId": song_ids},
            response_model=GetFavNumResponse,
        )
