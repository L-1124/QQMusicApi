"""专辑 Web 路由契约."""

from qqmusic_api.models.album import GetAlbumDetailResponse, GetAlbumSongResponse

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import VALUE, R

ROUTES: tuple[WebRoute, ...] = (
    R("album", "get_detail", "/album/{value}/detail", GetAlbumDetailResponse, params=VALUE, cache=PUBLIC_300),
    R(
        "album",
        "get_song",
        "/album/{value}/songs",
        GetAlbumSongResponse,
        params=VALUE,
        cache=PUBLIC_300,
    ),
)
