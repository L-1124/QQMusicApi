"""启动 Web API 服务."""

import logging
import sys
from pathlib import Path

import uvicorn

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _setup_logging(level: str) -> None:
    """配置标准 logging 输出格式与级别."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    logging.captureWarnings(capture=True)


if __name__ == "__main__":
    from web.src.core.config import settings

    _setup_logging(settings.logging.level)

    uvicorn.run(
        "web.src.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        limit_concurrency=settings.server.limit_concurrency,
        log_level=settings.logging.level.lower(),
        log_config=None,
    )
