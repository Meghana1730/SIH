"""Load config/*.yaml, apply environment overrides, validate, and cross-check the files.

Use `get_config()` in application code (loaded once, cached). Use `load_config()` in tests
or tools that need a specific folder or settings.
"""

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from app.config.base import quarter_index
from app.config.llm import KEYED_PROVIDERS, MODEL_PROVIDERS, LlmConfig
from app.config.scope import ScopeConfig
from app.config.scoring import ScoringConfig
from app.config.sectors import SectorsConfig
from app.config.synthetic import SyntheticConfig
from app.config.yaml_loader import DuplicateKeyError, UniqueKeyLoader
from app.core.settings import REPO_ROOT, Settings, get_settings
from app.models.base import EMBEDDING_DIM

# name -> (file, model)
FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "scoring": ("scoring.yaml", ScoringConfig),
    "sectors": ("sectors.yaml", SectorsConfig),
    "scope": ("scope.yaml", ScopeConfig),
    "llm": ("llm.yaml", LlmConfig),
    "synthetic": ("synthetic.yaml", SyntheticConfig),
}


class ConfigError(Exception):
    """The configuration is missing or invalid. The message names the file and the value."""


@dataclass(frozen=True)
class ProductConfig:
    """All product configuration, validated. Read-only."""

    scoring: ScoringConfig
    sectors: SectorsConfig
    scope: ScopeConfig
    llm: LlmConfig
    synthetic: SyntheticConfig
    # SHA-256 of scoring.yaml (line endings normalised). Stored with every pipeline run.
    scoring_sha256: str
    config_dir: Path
    # Environment variables that changed a YAML value (names only, never values).
    overrides: tuple[str, ...]

    @property
    def embedding_model_dir(self) -> Path:
        path = Path(self.llm.embeddings.local_path)
        return path if path.is_absolute() else REPO_ROOT / path

    def summary(self) -> str:
        llm, emb, syn = self.llm.llm, self.llm.embeddings, self.synthetic
        languages = ", ".join(self.scope.languages.supported)
        return "\n".join(
            [
                f"Configuration loaded from {self.config_dir}",
                f"  scoring.yaml    version {self.scoring.version} "
                f"(sha256 {self.scoring_sha256[:12]}...)",
                f"  sectors.yaml    {len(self.sectors.sectors)} sectors: "
                f"{', '.join(self.sectors.codes)}",
                f"  scope.yaml      {self.scope.state}: {len(self.scope.districts)} districts "
                f"({', '.join(self.scope.district_codes)}); languages {languages}",
                f"  llm.yaml        LLM provider {llm.provider} (mode {llm.mode}); embeddings "
                f"{'on' if emb.enabled else 'off'} ({emb.model_name}, {emb.dimension}-d)",
                f"  synthetic.yaml  seed {syn.seed}; history {syn.history.start_quarter}.."
                f"{syn.history.end_quarter} ({syn.history.quarter_count} quarters); "
                f"{len(syn.planted_patterns)} planted patterns",
                f"  env overrides   {', '.join(self.overrides) or 'none'}",
            ]
        )


# ---------------------------------------------------------------- helpers
def _display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Missing configuration file: {_display(path)}")
    try:
        # Repeated keys are refused (PyYAML would silently keep the last one).
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)  # noqa: S506
    except DuplicateKeyError as exc:
        raise ConfigError(f"{_display(path)}: {exc}") from None
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise ConfigError(f"{_display(path)} is not valid YAML{where}: {problem}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{_display(path)} must contain `key: value` lines at the top level")
    return data


def _validate(model: type[BaseModel], data: dict[str, Any], path: Path) -> BaseModel:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        lines = [f"Invalid configuration in {_display(path)}:"]
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "(top level)"
            if error["type"] == "extra_forbidden":
                message = "unknown key (check the spelling; extra keys are not allowed)"
            elif error["type"] == "missing":
                message = "required key is missing"
            else:
                message = error["msg"].removeprefix("Value error, ")
            lines.append(f"  - {location}: {message}")
        raise ConfigError("\n".join(lines)) from None


def scoring_file_sha256(path: Path) -> str:
    """Hash of scoring.yaml that is the same on Windows (CRLF) and Linux (LF)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _apply_overrides(raw: dict[str, dict[str, Any]], settings: Settings) -> list[str]:
    """Environment-specific switches that may replace YAML values (never business rules)."""
    applied: list[str] = []
    llm = raw["llm"].get("llm")
    if isinstance(llm, dict):
        if settings.llm_provider is not None:
            llm["provider"] = settings.llm_provider
            applied.append("LLM_PROVIDER")
        if settings.llm_mode is not None:
            llm["mode"] = settings.llm_mode
            applied.append("LLM_MODE")
        if settings.llm_max_calls_per_job is not None:
            llm["max_calls_per_job"] = settings.llm_max_calls_per_job
            applied.append("LLM_MAX_CALLS_PER_JOB")
        if settings.llm_model is not None:
            provider = llm.get("provider")
            if provider not in MODEL_PROVIDERS or not isinstance(llm.get("models"), dict):
                raise ConfigError(
                    f"LLM_MODEL is set, but the LLM provider '{provider}' does not use a model. "
                    "Set LLM_PROVIDER to ollama, openai or anthropic, or remove LLM_MODEL."
                )
            llm["models"][provider] = settings.llm_model
            applied.append("LLM_MODEL")
    embeddings = raw["llm"].get("embeddings")
    if isinstance(embeddings, dict):
        if settings.embeddings_enabled is not None:
            embeddings["enabled"] = settings.embeddings_enabled
            applied.append("EMBEDDINGS_ENABLED")
        if settings.embedding_model_path is not None:
            embeddings["local_path"] = settings.embedding_model_path
            applied.append("EMBEDDING_MODEL_PATH")
    if settings.synth_seed is not None:
        raw["synthetic"]["seed"] = settings.synth_seed
        applied.append("SYNTH_SEED")
    return applied


def _cross_check(
    scoring: ScoringConfig,
    sectors: SectorsConfig,
    scope: ScopeConfig,
    llm: LlmConfig,
    synthetic: SyntheticConfig,
    settings: Settings,
) -> list[str]:
    """Rules that involve more than one file (or the environment)."""
    problems: list[str] = []
    districts, sector_codes = set(scope.district_codes), set(sectors.codes)

    for pattern_id, pattern in synthetic.planted_patterns.items():
        for code in pattern.districts:
            if code not in districts:
                problems.append(
                    f"synthetic.yaml planted_patterns.{pattern_id}.districts: '{code}' is not "
                    "a district in scope.yaml"
                )
        for code in pattern.sectors:
            if code not in sector_codes:
                problems.append(
                    f"synthetic.yaml planted_patterns.{pattern_id}.sectors: '{code}' is not "
                    "a sector in sectors.yaml"
                )

    event = synthetic.demo_event
    if event.district not in districts:
        problems.append(
            f"synthetic.yaml demo_event.district: '{event.district}' is not in scope.yaml"
        )
    if event.sector not in sector_codes:
        problems.append(
            f"synthetic.yaml demo_event.sector: '{event.sector}' is not in sectors.yaml"
        )
    if quarter_index(event.announced_quarter) < quarter_index(synthetic.history.start_quarter):
        problems.append(
            "synthetic.yaml demo_event.announced_quarter is before history.start_quarter"
        )

    needed = max(scoring.forecast.history_quarters, scoring.trend.window_quarters)
    if synthetic.history.quarter_count < needed:
        problems.append(
            f"synthetic.yaml history covers {synthetic.history.quarter_count} quarters, but "
            f"scoring.yaml needs at least {needed} (forecast.history_quarters / "
            "trend.window_quarters)"
        )

    if llm.embeddings.dimension != EMBEDDING_DIM:
        problems.append(
            f"llm.yaml embeddings.dimension is {llm.embeddings.dimension}, but the database "
            f"stores {EMBEDDING_DIM}-number vectors (app/models/base.py EMBEDDING_DIM). "
            "Choose a matching model, or change the schema with a migration."
        )

    settings_llm = llm.llm
    if (
        settings_llm.mode == "live"
        and settings_llm.provider in KEYED_PROVIDERS
        and settings.llm_api_key is None
    ):
        problems.append(
            f"llm.yaml: mode 'live' with provider '{settings_llm.provider}' needs an API key. "
            "Set LLM_API_KEY in .env (never in llm.yaml)."
        )
    return problems


# ---------------------------------------------------------------- public API
def load_config(config_dir: Path | None = None, settings: Settings | None = None) -> ProductConfig:
    """Read and validate every config file. Raises ConfigError listing ALL problems found."""
    settings = settings or get_settings()
    directory = Path(config_dir) if config_dir is not None else settings.config_dir

    errors: list[str] = []
    raw: dict[str, dict[str, Any]] = {}
    for name, (file_name, _) in FILES.items():
        try:
            raw[name] = _read_yaml(directory / file_name)
        except ConfigError as exc:
            errors.append(str(exc))
    if errors:
        raise ConfigError("\n".join(errors))

    overrides = _apply_overrides(raw, settings)

    parsed: dict[str, BaseModel] = {}
    for name, (file_name, model) in FILES.items():
        try:
            parsed[name] = _validate(model, raw[name], directory / file_name)
        except ConfigError as exc:
            errors.append(str(exc))
    if errors:
        raise ConfigError("\n".join(errors))

    problems = _cross_check(**parsed, settings=settings)  # type: ignore[arg-type]
    if problems:
        raise ConfigError(
            "Configuration files do not agree:\n" + "\n".join(f"  - {p}" for p in problems)
        )

    return ProductConfig(
        **parsed,  # type: ignore[arg-type]
        scoring_sha256=scoring_file_sha256(directory / "scoring.yaml"),
        config_dir=directory,
        overrides=tuple(overrides),
    )


@lru_cache
def get_config() -> ProductConfig:
    """The application's configuration, loaded once from the folder in Settings.config_dir."""
    return load_config()
