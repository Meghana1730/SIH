"""FastAPI application entry point.

Run locally (from the backend/ folder, with the virtual environment active):
    uvicorn app.main:app --reload --port 8000
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api import admin, analytics, auth, directory, health, hello, ingestion
from app.config import ConfigError, get_config
from app.core.security import SecuritySettingsError, check_security_settings
from app.core.settings import get_settings

# uvicorn prints this logger's INFO messages, so the summary shows up in the console.
startup_log = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    settings = get_settings()
    # Refuse to start without a strong JWT secret (see .env.example).
    check_security_settings(settings)
    # Load and validate config/*.yaml now, so a bad file stops the app at startup
    # instead of causing wrong numbers later.
    config = get_config()
    startup_log.info(config.summary())

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.config = config

    # Health checks live at the root (/health, /health/db) so tools can find them easily.
    app.include_router(health.router)
    # Versioned product API.
    app.include_router(hello.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(directory.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(ingestion.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        # Opening http://localhost:8000 in a browser shows the interactive API docs.
        return RedirectResponse(url="/docs")

    return app


try:
    app = create_app()
except (ConfigError, SecuritySettingsError) as error:
    # Show only the readable problem (no long traceback), then stop.
    sys.stderr.write(f"\nKaushalSetu cannot start:\n{error}\n\n")
    raise SystemExit(1) from None
