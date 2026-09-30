"""Environment settings: things that differ per computer or deployment.

Values are read (in this order of priority) from real environment variables, then from
the repository-level ``.env`` file. See ``.env.example`` for the list.

Business rules (weights, thresholds, sectors, districts, ...) are NOT here. They live in the
YAML files in ``config/`` and are loaded by ``app.config``. Only a few environment-specific
switches (LLM provider/keys, embeddings on/off, synthetic seed) can override those files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# backend/app/core/settings.py -> parents[3] is the repository root (kaushalsetu/).
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # "LLM_PROVIDER=" (empty) in .env means "not set", not an empty string.
        env_ignore_empty=True,
    )

    app_name: str = "KaushalSetu API"
    app_version: str = "0.1.0"
    app_env: str = "dev"

    # ---------- database (shared with docker-compose.yml through .env) ----------
    postgres_user: str = "kaushal"
    postgres_password: str = ""
    postgres_db: str = "kaushalsetu"
    # 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 (::1) first and waits
    # for a timeout, because the container only listens on IPv4 127.0.0.1.
    postgres_host: str = "127.0.0.1"
    postgres_host_port: int = 5433
    # Optional full override, e.g. for CI or a hosted database. Empty means "build from parts".
    database_url: str | None = None
    db_connect_timeout_seconds: int = 3

    # ---------- product configuration (YAML) ----------
    # Folder with scoring.yaml, sectors.yaml, scope.yaml, llm.yaml, synthetic.yaml.
    config_dir: Path = REPO_ROOT / "config"

    # ---------- optional overrides of config/*.yaml (None = use the YAML value) ----------
    llm_provider: str | None = None  # LLM_PROVIDER: none | mock | ollama | openai | anthropic
    llm_mode: str | None = None  # LLM_MODE: off | cache_only | live
    llm_model: str | None = None  # LLM_MODEL: model for the active provider
    llm_max_calls_per_job: int | None = None  # LLM_MAX_CALLS_PER_JOB
    # Secret: only ever from the environment / .env, never from YAML files.
    llm_api_key: SecretStr | None = None  # LLM_API_KEY
    embeddings_enabled: bool | None = None  # EMBEDDINGS_ENABLED
    embedding_model_path: str | None = None  # EMBEDDING_MODEL_PATH
    synth_seed: int | None = None  # SYNTH_SEED

    # ---------- login tokens (JWT) ----------
    # JWT_SECRET has NO default on purpose: the app refuses to start without a long random
    # secret in .env (see app/core/security.py check_security_settings).
    jwt_secret: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_expires_minutes: int = Field(default=60, ge=5, le=1440)
    jwt_issuer: str = "kaushalsetu"
    jwt_audience: str = "kaushalsetu-api"

    # ---------- account protection ----------
    # Anyone may self-register, but ONLY as a candidate; staff accounts are created by an admin.
    auth_public_registration: bool = True
    auth_password_min_length: int = Field(default=10, ge=8, le=64)
    # Failed logins allowed per email address within the window, then 429 until it passes.
    auth_login_max_failures: int = Field(default=5, ge=1)
    # Login attempts (successful or not) allowed per client IP within the window.
    auth_login_max_attempts_per_ip: int = Field(default=30, ge=1)
    auth_login_window_seconds: int = Field(default=900, ge=1)
    # Registrations allowed per client IP per hour.
    auth_register_max_per_ip_per_hour: int = Field(default=10, ge=1)

    @field_validator("config_dir")
    @classmethod
    def _resolve_config_dir(cls, value: Path) -> Path:
        # A relative CONFIG_DIR is taken relative to the repository root.
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @property
    def sqlalchemy_url(self) -> URL | str:
        """Database URL for SQLAlchemy. URL.create() safely escapes special characters."""
        if self.database_url:
            return self.database_url
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_host_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
