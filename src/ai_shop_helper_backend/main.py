from fastapi import FastAPI

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.routers import auth, users

app = FastAPI(
    title=settings.PROJECT_NAME,
    root_path=settings.API_V1_STR,
    generate_unique_id_function=lambda route: f"{route.tags[0]}-{route.name}",
)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "OK"}
