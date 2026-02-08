# ai-shop-helper-backend

Backend for AI Shop Helper application.

## Setup

### Prerequisites

- uv installed. Follow instructions at [installing uv](https://docs.astral.sh/uv/getting-started/installation/).

## Install dependencies

```bash
uv sync
```

## Install pre-commit hooks

```bash
uv run pre-commit install
```

## Running the application

```bash
uv run fastapi run src/ai_shop_helper_backend/main.py --reload
```

## Running tests

```bash
uv run pytest
```

## Run docker development environment

```bash
uv docker compose up --build
```
