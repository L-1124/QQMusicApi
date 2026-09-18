"""专辑 Web 路由契约."""

from qqmusic_api.modules.album import AlbumApi

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(AlbumApi.get_detail, "/album/{value}/detail", cache=PUBLIC_300),
    R(
        AlbumApi.get_song,
        "/album/{value}/songs",
        cache=PUBLIC_300,
    ),
)
