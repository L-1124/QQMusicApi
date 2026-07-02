# === Builder stage ===
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies only — leverages Docker layer caching
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group web --frozen --no-install-project

# Copy source code and sync the full project
COPY qqmusic_api/ qqmusic_api/
COPY web/ web/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group web --frozen

# === Runtime stage ===
FROM python:3.12-slim

RUN groupadd --system --gid 999 appuser && \
    useradd --system --gid 999 --uid 999 --create-home appuser

COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    QQMUSIC_SERVER_HOST=0.0.0.0

USER appuser
WORKDIR /app

EXPOSE 8080

CMD ["python", "web/run.py"]
