# syntax=docker/dockerfile:1

# ---- builder: resolve and install dependencies into /app/.venv ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

# Compile .pyc at install time so the runtime image doesn't do it on first import.
# Copy (not hardlink) from the cache mount, which isn't part of the final layer.
# Use the image's Python rather than letting uv download its own.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first: this layer is only rebuilt when the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY app ./app

# ---- runtime: just the venv and the code ----
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

# Same path as in the builder: venv scripts have absolute paths baked in.
COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=prod

USER appuser

EXPOSE 8000

# Shell form is needed to expand $PORT; exec makes uvicorn PID 1 so it receives SIGTERM.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
