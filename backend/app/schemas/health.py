"""Response models for the health and hello endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    env: str
    # Which scoring settings (config/scoring.yaml) this API is running with.
    scoring_config_version: str
    scoring_config_sha256: str


class PgvectorStatus(BaseModel):
    installed: bool
    version: str | None = None


class DbHealthResponse(BaseModel):
    status: str
    database: str
    pgvector: PgvectorStatus


class DbHealthError(BaseModel):
    status: str
    database: str
    detail: str


class HelloResponse(BaseModel):
    message: str
