FROM ghcr.io/astral-sh/uv:python3.14-alpine3.23 AS builder
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY services/api ./services/api

# main app
FROM builder AS api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv -v sync --frozen --no-dev
CMD uv run --directory services/api fastapi run --workers 4 src/main.py

# db setup
FROM api AS db_setup
CMD uv run --directory services/api python -m scripts.db_init

# tests
FROM builder AS tests
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
CMD uv run --directory services/api pytest ${PYTEST_ARGS:-tests/integration}
