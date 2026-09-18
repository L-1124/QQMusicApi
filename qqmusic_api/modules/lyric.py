"""歌词相关 API."""

from typing import Any

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..models.lyric import (
    BatchGetMultiStyleTransLyricResponse,
    GetAIDictResponse,
    GetLyricResponse,
    GetSingingAnnotationsInfoResponse,
    IsAIDictExistsResponse,
)
from ._base import ApiModule


class LyricApi(ApiModule):
    """歌词相关 API."""

    @cgi_endpoint(
        key="lyric.get_lyric",
        module="music.musichallSong.PlayLyricInfo",
        method="GetPlayLyricInfo",
        response_model=GetLyricResponse,
    )
    def get_lyric(
        self,
        value: int | str,
        song_type: int = 1,
        *,
        qrc: bool = False,
        trans: bool = False,
        roma: bool = False,
        singing_annotations: bool = False,
    ) -> CgiRequestData:
        """获取歌词原始数据.

        Args:
            value: 歌曲 ID 或 MID.
            qrc: 是否获取逐字歌词.
            trans: 是否获取翻译.
            roma: 是否获取罗马音.
            singing_annotations: 是否获取助唱标注歌词.
            song_type: 歌曲类型.
        """
        params: dict[str, Any] = {
            "crypt": 1,
            "lrc_t": 0,
            "qrc": int(qrc),
            "qrc_t": 0,
            "roma": int(roma),
            "roma_t": 0,
            "trans": int(trans),
            "trans_t": 0,
            "needSingingAnnotations": singing_annotations,
            "type": song_type,
        }

        if isinstance(value, int) or (isinstance(value, str) and value.isdecimal()):
            params["songId"] = int(value)
        else:
            params["songMid"] = value

        return CgiRequestData(param=params, preserve_bool=True)

    @cgi_endpoint(
        key="lyric.get_singing_annotations_info",
        module="music.musichallSong.PlayLyricInfo",
        method="GetSingingAnnotationsInfo",
        response_model=GetSingingAnnotationsInfoResponse,
    )
    def get_singing_annotations_info(
        self,
        songid: int,
    ) -> CgiRequestData:
        """获取助唱标注歌词信息.

        Args:
            songid: 歌曲 ID.
        """
        return CgiRequestData(
            param={
                "songID": songid,
                "needNum": False,
            },
            preserve_bool=True,
        )

    @cgi_endpoint(
        key="lyric.get_multi_style_trans_lyric",
        module="music.musichallSong.PlayLyricInfo",
        method="BatchGetMultiStyleTransLyric",
        response_model=BatchGetMultiStyleTransLyricResponse,
    )
    def get_multi_style_trans_lyric(
        self,
        songid: int,
    ) -> CgiRequestData:
        """获取多风格翻译歌词 (如诗意、粤语、方言等).

        Args:
            songid: 歌曲 ID.
        """
        return CgiRequestData(param={"songID": songid})

    @cgi_endpoint(
        key="lyric.is_ai_dict_exists",
        module="music.musichallSong.PlayLyricInfo",
        method="IsAIDictExists",
        response_model=IsAIDictExistsResponse,
    )
    def is_ai_dict_exists(
        self,
        songid: int,
    ) -> CgiRequestData:
        """检查是否存在 AI 歌词词典.

        Args:
            songid: 歌曲 ID.
        """
        return CgiRequestData(param={"songID": songid})

    @cgi_endpoint(
        key="lyric.get_ai_dict",
        module="music.musichallSong.PlayLyricInfo",
        method="GetAIDictInfo",
        response_model=GetAIDictResponse,
    )
    def get_ai_dict(
        self,
        songid: int,
    ) -> CgiRequestData:
        """获取 AI 歌词词典信息.

        Args:
            songid: 歌曲 ID.
        """
        return CgiRequestData(param={"songID": songid})
