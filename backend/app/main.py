from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="arXiv semantic search",
    # Interactive docs are handy locally; no reason to expose them in prod.
    docs_url=None if settings.environment == "prod" else "/docs",
    redoc_url=None,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
