"""歌单相关 API."""

from qqmusic_api import ApiError

from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter
from ..models.request import Credential
from ..models.songlist import CreateDeleteSonglistResp, GetSonglistDetailResponse
from ._base import ApiModule


def _build_songlist_oper_param(
    dirid: int,
    song_info: list[tuple[int, int]],
    tid: int,
) -> dict[str, int | list[dict[str, int]]]:
    """构建歌单写操作的最小 JSON 参数."""
    return {
        "dirId": dirid,
        "tid": tid,
        "bFmtUtf8": True,
        "v_songInfo": [{"songId": song_id, "songType": song_type} for song_id, song_type in song_info],
    }


class SonglistApi(ApiModule):
    """歌单相关 API."""

    def get_detail(
        self,
        songlist_id: int,
        dirid: int = 0,
        num: int = 10,
        page: int = 1,
        *,
        onlysong: bool = False,
        tag: bool = True,
        userinfo: bool = True,
    ):
        """获取歌单详细信息和歌曲原始数据.

        Args:
            songlist_id: 歌单 ID.
            dirid: 目录 ID (可选).
            num: 返回歌曲数量.
            page: 页码.
            onlysong: 是否仅返回歌曲列表.
            tag: 是否返回标签信息.
            userinfo: 是否返回用户信息.
        """
        return self._build_request(
            module="music.srfDissInfo.DissInfo",
            method="CgiGetDiss",
            param={
                "disstid": songlist_id,
                "dirid": dirid,
                "tag": tag,
                "song_begin": num * (page - 1),
                "song_num": num,
                "userinfo": userinfo,
                "orderlist": True,
                "onlysonglist": onlysong,
            },
            response_model=GetSonglistDetailResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="song_begin", page_size_key="song_num"),
                adapter=ResponseAdapter(
                    has_more_flag="hasmore",
                    total="total",
                    count=lambda response: len(response.songs),
                ),
            ),
        )

    def create(self, dirname: str, *, credential: Credential | None = None):
        """创建歌单.

        Note:
            重名歌单并不会创建失败, 服务端会自动添加时间戳.

        Args:
            dirname: 歌单名称.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
            module="music.musicasset.PlaylistBaseWrite",
            method="AddPlaylist",
            param={"dirName": dirname},
            credential=target_credential,
            response_model=CreateDeleteSonglistResp,
        )

    def delete(self, dirid: int, *, credential: Credential | None = None):
        """删除歌单.

        Note:
            删除不存在歌单时返回的 dirid 为 0

        Args:
            dirid: 歌单目录 ID.
            credential: 登录凭证.
        """
        target_credential = self._require_login(credential)
        return self._build_request(
            module="music.musicasset.PlaylistBaseWrite",
            method="DelPlaylist",
            param={"dirId": dirid},
            credential=target_credential,
            response_model=CreateDeleteSonglistResp,
        )

    async def add_songs(
        self,
        dirid: int,
        song_info: list[tuple[int, int]],
        *,
        tid: int = 0,
        credential: Credential | None = None,
    ) -> bool:
        """添加歌曲到歌单.

        Args:
            dirid: 歌单目录 ID.
            song_info: 歌曲信息列表, 每项为 `(song_id, song_type)`.
            tid: 歌单 TID.
            credential: 登录凭证.

        Returns:
            操作成功与否 (歌曲已存在于歌单中也返回 True).
        """
        target_credential = self._require_login(credential)
        try:
            data = await self._build_request(
                module="music.musicasset.PlaylistDetailWrite",
                method="AddSonglist",
                param=_build_songlist_oper_param(dirid=dirid, song_info=song_info, tid=tid),
                credential=target_credential,
                preserve_bool=True,
            )
            return data.get("retCode") == 0
        except ApiError as e:
            if e.code == 80092:
                return False
            raise

    async def del_songs(
        self,
        dirid: int,
        song_info: list[tuple[int, int]],
        *,
        tid: int = 0,
        credential: Credential | None = None,
    ) -> bool:
        """删除歌单中的歌曲.

        Args:
            dirid: 歌单目录 ID.
            song_info: 歌曲信息列表, 每项为 `(song_id, song_type)`.
            tid: 歌单 TID.
            credential: 登录凭证.

        Returns:
            操作成功与否 (歌曲不存在于歌单中也返回 True).
        """
        target_credential = self._require_login(credential)
        songs = song_info or []
        try:
            data = await self._build_request(
                module="music.musicasset.PlaylistDetailWrite",
                method="DelSonglist",
                param=_build_songlist_oper_param(dirid=dirid, song_info=songs, tid=tid),
                credential=target_credential,
            )
            return data.get("retCode") == 0
        except ApiError as e:
            if e.code == 80092:
                return False
            raise
