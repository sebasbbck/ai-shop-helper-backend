FROM public.ecr.aws/amazonlinux/amazonlinux:latest AS base

RUN dnf update \
    && dnf install -y shadow-utils openssl-devel libffi-devel bzip2-devel python3.11 \
    && dnf clean all

RUN groupadd --system --gid 1001 nonroot \
    && useradd --system --uid 1001 --gid nonroot nonroot

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

FROM base AS migrate
COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/.venv
COPY --from=builder --chown=nonroot:nonroot /app/src /app/src
COPY --from=builder --chown=nonroot:nonroot /app/migrations /app/migrations
COPY --from=builder --chown=nonroot:nonroot /app/pyproject.toml /app/pyproject.toml

USER nonroot:nonroot
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

CMD ["alembic", "upgrade", "head"]

FROM base AS final
COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/.venv
COPY --from=builder --chown=nonroot:nonroot /app/src /app/src

USER nonroot:nonroot
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

CMD ["fastapi", "run", "src/ai_shop_helper_backend/main.py", "--port", "8080", "--reload"]
