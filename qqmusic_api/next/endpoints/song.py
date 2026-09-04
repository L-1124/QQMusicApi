"""歌曲模块端点声明 (试点). 声明内容必须与 modules/song.py 的描述符构造保持一致."""

from ...core.versioning import Platform
from ...models.song import GetSongDetailResponse, GetSongUrlsResponse, QuerySongResponse
from ...modules.song import BaseSongFileType, EncryptedSongFileType
from ..endpoint import CgiEndpoint

GET_SONG_DETAIL = CgiEndpoint(
    module="music.pf_song_detail_svr",
    method="get_song_detail_yqq",
    platform=Platform.WEB,
    response_model=GetSongDetailResponse,
)

QUERY_SONG = CgiEndpoint(
    module="music.trackInfo.UniformRuleCtrl",
    method="CgiGetTrackInfo",
    response_model=QuerySongResponse,
)


def song_urls_endpoint(file_type: BaseSongFileType) -> CgiEndpoint:
    """按顶层文件类型选择明文或加密 vkey 端点.

    Args:
        file_type: 歌曲文件类型; 传入 EncryptedSongFileType 时选择加密端点.

    Returns:
        对应的歌曲链接端点声明.
    """
    if isinstance(file_type, EncryptedSongFileType):
        return CgiEndpoint(
            module="music.vkey.GetEVkey",
            method="CgiGetEVkey",
            response_model=GetSongUrlsResponse,
        )
    return CgiEndpoint(
        module="music.vkey.GetVkey",
        method="UrlGetVkey",
        response_model=GetSongUrlsResponse,
    )
