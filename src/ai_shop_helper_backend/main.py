from fastapi import FastAPI

app = FastAPI(root_path="/api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None) -> dict[str, int | str | None]:
    return {"item_id": item_id, "q": q}


@app.get("/health/db")
def health_db() -> dict[str, str]:
    import os
    import psycopg

    try:
        connection = psycopg.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME"),
        )
        connection.execute("SELECT 1")
        connection.close()
        return {"status": "ok"}
    except:
        return {"status": "failed"}


def _n8n_endpoint(path: str) -> dict[str, str]:
    import os
    import httpx

    try:
        n8n_url = os.getenv("N8N_URL")
        response = httpx.get(f"{n8n_url}{path}", timeout=5.0)
        response.raise_for_status()
        return {"status": "ok"}
    except:
        return {"status": "failed"}


@app.get("/health/n8n")
def health_n8n() -> dict[str, str]:
    return _n8n_endpoint("/healthz")


@app.get("/health/n8n/db")
def health_n8n_db() -> dict[str, str]:
    return _n8n_endpoint("/healthz/readiness")


@app.get("/health/n8n/webhook")
def health_n8n_webhook() -> dict[str, str]:
    return _n8n_endpoint("/webhook/health")
