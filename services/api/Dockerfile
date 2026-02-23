FROM ghcr.io/astral-sh/uv:python3.14-alpine AS builder
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY services/api ./services/api

# main app
FROM builder AS api
# COPY services/api ./services/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv -v sync --frozen --no-dev
CMD uv run --directory services/api fastapi run --workers 4 src/main.py

# db setup
FROM api as db_setup
CMD uv run --directory services/api python -m scripts.db_init
# CMD uv run --directory services/api python -m scripts.db_init_cli

# migrations
# FROM db_setup as py_migrate
# CMD uv run --directory services/api alembic upgrade head

# e2e
FROM builder as e2e
# COPY services/api ./services/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
CMD uv run pytest -m e2e
