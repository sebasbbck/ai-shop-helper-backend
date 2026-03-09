from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.db import engine
from ai_shop_helper_backend.routers import auth, n8n_test, users


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager to handle startup and shutdown events.

    Dispose of the database engine on shutdown to ensure all connections are properly closed.
    """
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    root_path=settings.API_V1_STR,
    generate_unique_id_function=lambda route: f"{route.tags[0]}-{route.name}",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,  # ty:ignore[invalid-argument-type]
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(n8n_test.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "OK"}
