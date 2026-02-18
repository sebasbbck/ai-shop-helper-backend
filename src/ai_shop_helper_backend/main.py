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
