"""歌词相关 API."""

from typing import Any

from ._base import ApiModule


class LyricApi(ApiModule):
    """歌词相关 API."""

    def get_lyric(
        self,
        value: str | int,
        *,
        qrc: bool = False,
        trans: bool = False,
        roma: bool = False,
    ):
        """获取歌词原始数据.

        Args:
            value: 歌曲 ID 或 MID.
            qrc: 是否获取逐字歌词 (逐字歌词可能需要特定权限).
            trans: 是否获取翻译.
            roma: 是否获取罗马音.
        """
        params: dict[str, Any] = {
            "crypt": 1,
            "lrc_t": 0,
            "qrc": qrc,
            "qrc_t": 0,
            "roma": roma,
            "roma_t": 0,
            "trans": trans,
            "trans_t": 0,
            "type": 1,
        }
        params.update(self._build_query_common_params())
        if isinstance(value, int):
            params["songId"] = value
        else:
            params["songMid"] = value

        return self._build_request(
            module="music.musichallSong.PlayLyricInfo",
            method="GetPlayLyricInfo",
            param=params,
        )
