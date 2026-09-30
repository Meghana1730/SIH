"""Health endpoints.

- ``GET /health``    : is the API process running? (never touches the database)
- ``GET /health/db`` : can the API reach PostgreSQL, and is the pgvector extension enabled?
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_config
from app.core.db import get_db
from app.core.settings import get_settings
from app.schemas.health import DbHealthError, DbHealthResponse, HealthResponse, PgvectorStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    config = get_config()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        scoring_config_version=config.scoring.version,
        scoring_config_sha256=config.scoring_sha256,
    )


@router.get(
    "/health/db",
    response_model=DbHealthResponse,
    responses={503: {"model": DbHealthError, "description": "Database unreachable"}},
)
def health_db(db: Annotated[Session, Depends(get_db)]) -> DbHealthResponse | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
        pgvector_version = db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        # Log the error type only: connection errors can contain host/user details.
        logger.warning("Database health check failed: %s", exc.__class__.__name__)
        error = DbHealthError(status="error", database="unreachable", detail=exc.__class__.__name__)
        return JSONResponse(status_code=503, content=error.model_dump())

    return DbHealthResponse(
        status="ok",
        database="connected",
        pgvector=PgvectorStatus(installed=pgvector_version is not None, version=pgvector_version),
    )
