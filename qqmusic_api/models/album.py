"""专辑模型."""

from pydantic import BaseModel, Field


class AlbumSongItem(BaseModel):
    """专辑歌曲条目."""

    song_info: dict = Field(alias="songInfo")


class AlbumSongResponse(BaseModel):
    """专辑歌曲响应."""

    song_list: list[AlbumSongItem] = Field(alias="songList")
    total_num: int = Field(alias="totalNum")
