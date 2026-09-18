"""专辑 Web 路由契约."""

from qqmusic_api.modules.album import AlbumApi

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import VALUE, R

ROUTES: tuple[WebRoute, ...] = (
    R(AlbumApi.get_detail, "/album/{value}/detail", params=VALUE, cache=PUBLIC_300),
    R(
        AlbumApi.get_song,
        "/album/{value}/songs",
        params=VALUE,
        cache=PUBLIC_300,
    ),
)
