"""业务模块包。"""

from .album import AlbumApi
from .comment import CommentApi
from .mv import MvApi
from .recommend import RecommendApi
from .top import TopApi

__all__ = ["AlbumApi", "CommentApi", "MvApi", "RecommendApi", "TopApi"]
