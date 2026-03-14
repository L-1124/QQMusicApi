"""歌曲相关 API 模块."""

from enum import Enum
from random import choice
from time import time
from typing import Any, overload

from ..utils.common import get_guid
from ._base import ApiModule


def _as_str_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if any(not isinstance(key, str) for key in value):
        return None
    return value


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
        )

    def get_try_url(self, mid: str, vs: str):
        """获取试听文件链接原始数据.

        Args:
            mid: 歌曲 MID.
            vs: 歌曲 vs 标识.
        """
        return self._build_request(
            module="music.vkey.GetVkey",
            method="UrlGetVkey",
            param={
                "filename": [f"RS02{vs}.mp3"],
                "guid": get_guid(),
                "songmid": [mid],
                "songtype": [1],
            },
        )

    async def _get_cdn_dispatch(
        self,
        *,
        force_refresh: bool = False,
        use_new_domain: bool = True,
        use_ipv6: bool = True,
    ) -> None:
        """获取并缓存音频 CDN 调度信息.

        Args:
            force_refresh: 是否强制刷新缓存.
            use_new_domain: 是否启用新域名.
            use_ipv6: 是否启用 IPv6.
        """
        now = time()
        cached_data = self._song_url_dispatch_data
        refresh_at = self._song_url_dispatch_refresh_at

        if not force_refresh and cached_data is not None and now < refresh_at:
            return

        data = await self._client.execute(
            self._build_request(
                module="music.audioCdnDispatch.cdnDispatch",
                method="GetCdnDispatch",
                param={
                    "guid": get_guid(),
                    "uid": "0",
                    "use_new_domain": int(use_new_domain),
                    "use_ipv6": int(use_ipv6),
                },
            ),
        )

        payload = _as_str_dict(data)
        if payload is None:
            raise TypeError("GetCdnDispatch 返回了非字符串键字典")

        self._song_url_dispatch_data = payload
        sip = payload.get("sip", [])
        if isinstance(sip, list):
            self._SONG_URL_DOMAINS = tuple(item for item in sip if isinstance(item, str))
        else:
            self._SONG_URL_DOMAINS = ()
        self._song_url_domain_infos = {
            item["cdn"]: item
            for item in payload.get("sipinfo", [])
            if isinstance(item, dict) and isinstance(item.get("cdn"), str)
        }
        now = time()
        refresh_time = payload.get("refreshTime", 0)
        expiration = payload.get("expiration", 0)
        cache_time = payload.get("cacheTime", 0)
        self._song_url_dispatch_refresh_at = now + (refresh_time if isinstance(refresh_time, int | float) else 0)
        if isinstance(expiration, int | float) and isinstance(cache_time, int | float):
            self._song_url_dispatch_expire_at = now + min(expiration, cache_time)
        else:
            self._song_url_dispatch_expire_at = now

    def _choose_song_url_domain(self) -> str:
        """选择当前使用的歌曲下载域名."""
        if not self._SONG_URL_DOMAINS:
            return self._SONG_URL_FALLBACK_DOMAIN
        return choice(list(self._SONG_URL_DOMAINS))

    @overload
    async def get_song_urls(
        self,
        mid: list[str],
        file_type: SongFileType = SongFileType.MP3_128,
    ) -> dict[str, str]: ...

    @overload
    async def get_song_urls(
        self,
        mid: list[str],
        file_type: EncryptedSongFileType,
    ) -> dict[str, tuple[str, str]]: ...

    async def get_song_urls(
        self,
        mid: list[str],
        file_type: SongFileType | EncryptedSongFileType = SongFileType.MP3_128,
    ) -> dict[str, str] | dict[str, tuple[str, str]]:
        """获取歌曲文件链接.

        Args:
            mid: 歌曲 MID 列表.
            file_type: 歌曲文件类型.

        Returns:
            dict[str, str] | dict[str, tuple[str, str]]: 普通类型返回下载链接映射,
            加密类型返回 `(链接, ekey)` 映射.
        """
        if not mid:
            return {}

        await self._get_cdn_dispatch()

        encrypted = isinstance(file_type, EncryptedSongFileType)
        module, method = (
            ("music.vkey.GetVkey", "UrlGetVkey") if not encrypted else ("music.vkey.GetEVkey", "CgiGetEVkey")
        )

        request_group = self._client.request_group()
        for mid_chunk_start in range(0, len(mid), 100):
            chunk = mid[mid_chunk_start : mid_chunk_start + 100]
            request_group.add(
                self._build_request(
                    module=module,
                    method=method,
                    param={
                        "filename": [f"{file_type.s}{item}{item}{file_type.e}" for item in chunk],
                        "guid": get_guid(),
                        "songmid": chunk,
                        "songtype": [0] * len(chunk),
                    },
                ),
            )

        raw_results = await request_group.execute()
        if encrypted:
            encrypted_result: dict[str, tuple[str, str]] = {}
            for raw in raw_results:
                if isinstance(raw, Exception):
                    raise raw
                payload = _as_str_dict(raw)
                if payload is None:
                    continue
                self._merge_encrypted_song_urls(encrypted_result, payload)
            return encrypted_result

        plain_result: dict[str, str] = {}
        for raw in raw_results:
            if isinstance(raw, Exception):
                raise raw
            payload = _as_str_dict(raw)
            if payload is None:
                continue
            self._merge_song_urls(plain_result, payload)
        return plain_result

    def _merge_song_urls(
        self,
        result: dict[str, str],
        raw: dict[str, Any],
    ) -> None:
        """合并单批歌曲链接结果.

        Args:
            result: 待更新的聚合结果.
            raw: 单批原始响应数据.
        """
        midurlinfo = raw.get("midurlinfo", [])
        if not isinstance(midurlinfo, list):
            return

        for info in midurlinfo:
            if not isinstance(info, dict):
                continue
            songmid = info.get("songmid")
            if not isinstance(songmid, str):
                continue

            path = info.get("purl") or info.get("wifiurl") or ""
            url = f"{self._choose_song_url_domain()}{path}" if path else ""
            result[songmid] = url

    def _merge_encrypted_song_urls(
        self,
        result: dict[str, tuple[str, str]],
        raw: dict[str, Any],
    ) -> None:
        """合并单批加密歌曲链接结果.

        Args:
            result: 待更新的聚合结果.
            raw: 单批原始响应数据.
        """
        midurlinfo = raw.get("midurlinfo", [])
        if not isinstance(midurlinfo, list):
            return

        for info in midurlinfo:
            if not isinstance(info, dict):
                continue
            songmid = info.get("songmid")
            if not isinstance(songmid, str):
                continue

            path = info.get("purl") or info.get("wifiurl") or ""
            url = f"{self._choose_song_url_domain()}{path}" if path else ""
            result[songmid] = (url, str(info.get("ekey", "")))

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
        )

    def get_related_songlist(self, songid: int):
        """获取歌曲相关歌单.

        Args:
            songid: 歌曲 ID.
        """
        return self._build_request(
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
        return self._build_request(
            module="MvService.MvInfoProServer",
            method="GetSongRelatedMv",
            param=params,
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
        )

    def get_fav_num(self, songid: list[int]):
        """获取歌曲收藏数量原始数据.

        Args:
            songid: 歌曲 ID 列表.
        """
        return self._build_request(
            module="music.musicasset.SongFavRead",
            method="GetSongFansNumberById",
            param={"v_songId": songid},
        )
