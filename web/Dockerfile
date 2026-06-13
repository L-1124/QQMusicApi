FROM python:3.14-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY qqmusic_api/ qqmusic_api/
COPY web/ web/

RUN uv sync --group web --no-dev --frozen

RUN adduser --system --no-create-home appuser
USER appuser

ENV QQMUSIC_SERVER_HOST=0.0.0.0

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD uv run --no-sync python -c "from urllib.request import urlopen; urlopen('http://localhost:8080/')" || exit 1

CMD ["uv", "run", "--no-sync", "web/run.py"]
