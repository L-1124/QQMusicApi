import logging
import os
import sys

from . import album, comment, login, lyric, mv, search, singer, song, songlist, top, user
from .utils.credential import Credential
from .utils.session import Session, get_session, set_session

__version__ = "0.4.1"

logger = logging.getLogger("qqmusicapi")

# Change to the "Selector" event loop if platform is Windows
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import WindowsSelectorEventLoopPolicy, set_event_loop_policy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())


__all__ = [
    "Credential",
    "Session",
    "album",
    "comment",
    "get_session",
    "login",
    "lyric",
    "mv",
    "search",
    "set_session",
    "singer",
    "song",
    "songlist",
    "top",
    "user",
]
