"""启动 Web API 服务."""

import sys
from pathlib import Path

import uvicorn

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


if __name__ == "__main__":
    from web.src.config import settings

    uvicorn.run(
        "web.src.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        reload=True,
        limit_concurrency=settings.server.limit_concurrency,
    )
