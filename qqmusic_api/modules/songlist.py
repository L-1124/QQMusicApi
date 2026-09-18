"""歌单相关 API."""

from ..core import CgiApiException
from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import OffsetStrategy
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

    @cgi_endpoint(
        key="songlist.get_detail",
        module="music.srfDissInfo.DissInfo",
        method="CgiGetDiss",
        response_model=GetSonglistDetailResponse,
    )
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
    ) -> CgiRequestData:
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
        return CgiRequestData(
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
            pager_strategy=OffsetStrategy[GetSonglistDetailResponse](
                offset_key="song_begin",
                page_size_key="song_num",
                has_more_extractor=lambda r: bool(r.hasmore),
                total_extractor=lambda r: r.total,
                count_extractor=lambda response: len(response.songs),
            ),
            items_extractor=lambda r: r.songs,
        )

    @cgi_endpoint(
        key="songlist.create",
        module="music.musicasset.PlaylistBaseWrite",
        method="AddPlaylist",
        response_model=CreateDeleteSonglistResp,
        require_login=True,
    )
    def create(self, dirname: str, *, credential: Credential | None = None) -> CgiRequestData:
        """创建歌单.

        Note:
            重名歌单并不会创建失败, 服务端会自动添加时间戳.

        Args:
            dirname: 歌单名称.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"dirName": dirname},
            credential=credential,
        )

    @cgi_endpoint(
        key="songlist.delete",
        module="music.musicasset.PlaylistBaseWrite",
        method="DelPlaylist",
        response_model=CreateDeleteSonglistResp,
        require_login=True,
    )
    def delete(self, dirid: int, *, credential: Credential | None = None) -> CgiRequestData:
        """删除歌单.

        Note:
            删除不存在歌单时返回的 dirid 为 0

        Args:
            dirid: 歌单目录 ID.
            credential: 登录凭证.
        """
        return CgiRequestData(
            param={"dirId": dirid},
            credential=credential,
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
        try:
            data = await self._build_cgi(
                module="music.musicasset.PlaylistDetailWrite",
                method="AddSonglist",
                param=_build_songlist_oper_param(dirid=dirid, song_info=song_info, tid=tid),
                credential=credential,
                require_login=True,
                preserve_bool=True,
            )
            return data.get("retCode") == 0
        except CgiApiException as e:
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
        songs = song_info or []
        try:
            data = await self._build_cgi(
                module="music.musicasset.PlaylistDetailWrite",
                method="DelSonglist",
                param=_build_songlist_oper_param(dirid=dirid, song_info=songs, tid=tid),
                credential=credential,
                require_login=True,
            )
            return data.get("retCode") == 0
        except CgiApiException as e:
            if e.code == 80092:
                return False
            raise

    async def like_song(
        self,
        song_info: list[tuple[int, int]],
        *,
        credential: Credential | None = None,
    ) -> bool:
        """收藏歌曲到 "我喜欢" 歌单.

        Note:
            "我喜欢" 歌单的目录 ID 固定为 201, 本方法即以 dirid=201 调用 `add_songs`.

        Args:
            song_info: 歌曲信息列表, 每项为 `(song_id, song_type)`.
            credential: 登录凭证.

        Returns:
            操作成功与否 (歌曲已在 "我喜欢" 中也返回 True).
        """
        return await self.add_songs(201, song_info, credential=credential)

    async def unlike_song(
        self,
        song_info: list[tuple[int, int]],
        *,
        credential: Credential | None = None,
    ) -> bool:
        """从 "我喜欢" 歌单移除歌曲.

        Note:
            "我喜欢" 歌单的目录 ID 固定为 201, 本方法即以 dirid=201 调用 `del_songs`.

        Args:
            song_info: 歌曲信息列表, 每项为 `(song_id, song_type)`.
            credential: 登录凭证.

        Returns:
            操作成功与否 (歌曲不在 "我喜欢" 中也返回 True).
        """
        return await self.del_songs(201, song_info, credential=credential)
