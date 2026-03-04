# AI Shop Helper Backend

Backend for the AI Shop Helper application. Built with FastAPI, SQLModel, and PostgreSQL.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — package manager
- [Docker](https://docs.docker.com/get-docker/) — for local development and integration tests

## Setup

```bash
# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Copy environment variables
cp .env.example .env
```

## Running the application

```bash
# With Docker (app + PostgreSQL)
docker compose up --build

# Also start Adminer at :8081
docker compose --profile tools up

# Without Docker (requires a running PostgreSQL)
uv run fastapi run src/ai_shop_helper_backend/main.py --reload
```

The app runs on port **8080**. API base path: `/api/v1`.

## Database migrations

```bash
# Apply migrations
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "description"
```

## Testing

```bash
# Unit tests only (fast, no Docker required)
uv run pytest

# Unit + integration tests (requires Docker for testcontainers)
uv run pytest tests/

# Single test
uv run pytest tests/path/to/test_file.py::ClassName::test_name
```

Coverage is enforced at **80%** minimum — the CI pipeline will reject PRs below this threshold.

## Code quality

```bash
# Format
uv run ruff format src/

# Lint with auto-fix
uv run ruff check --fix src/

# Type check
uv run ty check src/
```

## Architecture

```
src/ai_shop_helper_backend/
├── main.py          # FastAPI app, router registration, lifespan
├── core/
│   ├── config.py    # Settings via env vars (pydantic-settings)
│   ├── db.py        # Async engine + session factory
│   ├── security.py  # JWT creation/validation, password hashing (Argon2)
│   ├── deps.py      # FastAPI dependencies: get_session, get_current_user
│   └── utils.py     # UTC datetime helper
├── routers/
│   ├── auth.py      # /auth: register, login, refresh, logout
│   └── users.py     # /users: CRUD, superuser-protected routes
├── models/          # SQLModel table models (users, refreshtoken, mixins)
├── schemas/         # Pydantic schemas for request/response
└── services/
    └── users.py     # User business logic layer
migrations/          # Alembic migrations
```

### Authentication

- Login returns an access JWT (Bearer, 30 min) + refresh token in HTTP-only cookie (30 days)
- Refresh tokens are stored in the DB and rotated on each use
- Logout revokes only the current device's refresh token
- Superuser routes use a separate `get_current_superuser` dependency
