"""歌单相关 API。"""

from ..models import Credential
from ._base import ApiModule


class SonglistApi(ApiModule):
    """歌单相关 API。"""

    def get_detail(
        self,
        songlist_id: int,
        dirid: int = 0,
        num: int = 10,
        page: int = 1,
        onlysong: bool = False,
        tag: bool = True,
        userinfo: bool = True,
    ):
        """获取歌单详细信息和歌曲原始数据。"""
        return self.build_request(
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
        )

    def create(self, dirname: str, *, credential: Credential | None = None):
        """创建歌单。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.musicasset.PlaylistBaseWrite",
            method="AddPlaylist",
            param={"dirName": dirname},
            credential=target_credential,
        )

    def delete(self, dirid: int, *, credential: Credential | None = None):
        """删除歌单。"""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="music.musicasset.PlaylistBaseWrite",
            method="DelPlaylist",
            param={"dirId": dirid},
            credential=target_credential,
        )

    def add_songs(
        self,
        dirid: int = 1,
        song_ids: list[int] | None = None,
        *,
        credential: Credential | None = None,
    ):
        """添加歌曲到歌单。"""
        target_credential = self._require_login(credential)
        songs = song_ids or []
        return self.build_request(
            module="music.musicasset.PlaylistDetailWrite",
            method="AddSonglist",
            param={
                "dirId": dirid,
                "v_songInfo": [{"songType": 0, "songId": songid} for songid in songs],
            },
            credential=target_credential,
        )

    def del_songs(
        self,
        dirid: int = 1,
        song_ids: list[int] | None = None,
        *,
        credential: Credential | None = None,
    ):
        """删除歌单中的歌曲。"""
        target_credential = self._require_login(credential)
        songs = song_ids or []
        return self.build_request(
            module="music.musicasset.PlaylistDetailWrite",
            method="DelSonglist",
            param={
                "dirId": dirid,
                "v_songInfo": [{"songType": 0, "songId": songid} for songid in songs],
            },
            credential=target_credential,
        )
