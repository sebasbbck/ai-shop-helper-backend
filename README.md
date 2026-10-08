# AI Shop Helper Backend

Backend for the AI Shop Helper application. Built with FastAPI, SQLModel, and PostgreSQL.

> AI Shop Helper was a SaaS platform where online stores connect their website (WordPress) and analytics (Google Analytics 4, Search Console) to run AI agents on their projects. It was developed by a small team during 2026; this repository is republished with the company's permission. The frontend lives in [ai-shop-helper-frontend](https://github.com/sebasbbck/ai-shop-helper-frontend).

## My contribution

I worked on this backend as a developer intern (June–September 2026), shipping features end to end through pull requests reviewed by the tech lead:

- **In-app notification system** — data model, REST API and dispatch logic. Chose REST polling over SSE / PostgreSQL `LISTEN/NOTIFY` because the backend runs as several instances behind a load balancer. Includes role-aware dispatch (e.g. billing alerts only reach org owners), per-type muting enforced server-side, and i18n-ready payloads (the backend sends `type` + `payload`, the frontend renders the text).
- **Notification triggers** — wired real events into the system: agent run finished/failed, billing (credits granted, failed payment, cancelled subscription), new connections and account activation changes.
- **Notifications inbox API** — mark as read/unread, mark all as read and filtering by organization.
- **Google OAuth2** — sign-in with Google (CSRF-protected state, account linking by verified email) and, separately, a per-project Google connection for GA4 and Search Console with encrypted, auto-refreshing tokens. Reworked the original design after code review to split login from data access.
- **Dynamic connection availability** — endpoint that derives which integrations a project needs from its agents' steps, so the UI doesn't hardcode them.
- **Testing and CI** — unit tests with mocked sessions and integration tests against a real PostgreSQL (testcontainers), keeping coverage above the 80% CI gate.

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
