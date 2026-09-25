import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session

settings = get_settings()

app = FastAPI(
    title="arXiv semantic search",
    # Interactive docs are handy locally; no reason to expose them in prod.
    docs_url=None if settings.environment == "prod" else "/docs",
    redoc_url=None,
)

# Long enough for Neon to wake from scale-to-zero, short enough not to hang the caller.
HEALTH_DB_TIMEOUT_S = 5


@app.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    try:
        async with asyncio.timeout(HEALTH_DB_TIMEOUT_S):
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
