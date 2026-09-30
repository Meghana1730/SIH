"""Tests for the YAML configuration (config/*.yaml) and its validation.

Invalid-configuration tests copy the real config folder to a temporary folder, break one
thing, and check that loading fails with a clear message naming the file and the value.
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import pytest
import yaml
from pydantic import BaseModel

from app.config import ConfigError, load_config
from app.config.base import ConfigModel
from app.config.llm import LlmConfig
from app.config.loader import scoring_file_sha256
from app.config.scope import ScopeConfig
from app.config.scoring import ScoringConfig
from app.config.sectors import SectorsConfig
from app.config.synthetic import SyntheticConfig
from app.core.settings import REPO_ROOT, Settings

REAL_CONFIG_DIR = REPO_ROOT / "config"
OVERRIDE_VARIABLES = [
    "CONFIG_DIR",
    "LLM_PROVIDER",
    "LLM_MODE",
    "LLM_MODEL",
    "LLM_MAX_CALLS_PER_JOB",
    "LLM_API_KEY",
    "EMBEDDINGS_ENABLED",
    "EMBEDDING_MODEL_PATH",
    "SYNTH_SEED",
]


@pytest.fixture(autouse=True)
def _no_override_variables(monkeypatch):
    """Tests must not depend on override variables set on the developer's machine."""
    for name in OVERRIDE_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def settings(**values: Any) -> Settings:
    """Settings that ignore the .env file, with only the given overrides."""
    return Settings(_env_file=None, **values)


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(REAL_CONFIG_DIR, target)
    return target


def edit(directory: Path, file_name: str, change: Callable[[dict], None]) -> None:
    path = directory / file_name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_error(directory: Path, **values: Any) -> str:
    with pytest.raises(ConfigError) as error:
        load_config(directory, settings(**values))
    return str(error.value)


# ---------------------------------------------------------------- the real files
def test_real_configuration_loads_with_the_agreed_values():
    config = load_config(settings=settings())
    s = config.scoring

    assert s.demand.weights.model_dump() == {
        "postings": 0.35,
        "employer_survey": 0.25,
        "growth_events": 0.20,
        "absorption": 0.20,
    }
    assert s.demand.missing_components == "renormalize"
    assert (s.mismatch.undersupplied_below, s.mismatch.oversupplied_above) == (0.7, 1.5)
    assert s.course_health.weights.model_dump() == {
        "placement_rate": 0.30,
        "work_relevance": 0.10,
        "recency": 0.10,
        "demand_trend": 0.20,
        "skill_coverage": 0.30,
    }
    assert s.trend.window_quarters == 4
    assert s.trend.emerging.min_relative_growth == 0.25
    assert s.trend.emerging.min_mentions == 20
    assert s.trend.declining.consecutive_quarter_drops == 3
    assert s.trend.declining.min_relative_decline == 0.20
    assert s.trend.emerging.external_trend.enabled is False  # "strong" not defined yet

    assert config.sectors.codes == ["ELECTRICAL", "EV", "SOLAR_PV"]
    assert config.scope.district_codes == ["MH-PUNE", "MH-NASHIK", "MH-NAGPUR", "MH-KOLHAPUR"]
    assert config.scope.languages.supported == ["en", "hi", "mr"]
    # The free, deterministic mock is the default LLM: the prototype costs Rs 0.
    assert (config.llm.llm.provider, config.llm.llm.mode) == ("mock", "live")
    assert config.llm.llm.tasks.skill_phrase_extraction.enabled is False
    assert config.llm.embeddings.dimension == 384
    assert config.synthetic.history.quarter_count == 6
    assert len(config.scoring_sha256) == 64
    assert config.overrides == ()


def test_missing_demand_component_weights_are_renormalized():
    weights = load_config(settings=settings()).scoring.demand.weights

    # No employer-survey data: the other three are scaled up to add to 1.0 again.
    scaled = weights.renormalized({"postings", "growth_events", "absorption"})
    assert scaled == pytest.approx(
        {"postings": 0.35 / 0.75, "growth_events": 0.20 / 0.75, "absorption": 0.20 / 0.75}
    )
    assert sum(scaled.values()) == pytest.approx(1.0)

    # All components present: unchanged.
    assert weights.renormalized(weights.model_dump()) == pytest.approx(weights.model_dump())

    with pytest.raises(ValueError, match="unknown demand components"):
        weights.renormalized({"postings", "tweets"})
    with pytest.raises(ValueError, match="no demand component"):
        weights.renormalized(set())


def fields_with_python_defaults(model: type[BaseModel], path: str = "") -> list[str]:
    """All fields (also inside nested models, lists and dicts) that have a Python default."""
    found = []
    for name, field in model.model_fields.items():
        here = f"{path or model.__name__}.{name}"
        if not field.is_required():
            found.append(here)
        pending = [field.annotation]
        while pending:  # look inside list[...], dict[...], X | None, Annotated[...]
            annotation = pending.pop()
            if isinstance(annotation, type) and issubclass(annotation, ConfigModel):
                found += fields_with_python_defaults(annotation, here)
            pending += list(get_args(annotation))
    return found


def test_business_values_have_no_python_defaults():
    """Every business value must come from YAML: no model field may have a default."""
    models = [ScoringConfig, SectorsConfig, ScopeConfig, LlmConfig, SyntheticConfig]
    assert [p for m in models for p in fields_with_python_defaults(m)] == []


def test_the_default_detector_really_detects_defaults():
    class Inner(ConfigModel):
        threshold: float = 0.5  # a hidden Python default

    class Outer(ConfigModel):
        items: list[Inner]

    assert fields_with_python_defaults(Outer) == ["Outer.items.threshold"]


# ---------------------------------------------------------------- invalid values
def test_demand_weights_must_add_up_to_one(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["demand"]["weights"].update(postings=0.45))
    message = load_error(config_dir)
    assert "scoring.yaml" in message
    assert "demand.weights" in message
    assert "must add up to 1.0 but add up to 1.1" in message


def test_course_health_weights_must_add_up_to_one(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["course_health"]["weights"].update(recency=0.2))
    assert "course_health.weights" in load_error(config_dir)


def test_mismatch_thresholds_must_be_in_order(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["mismatch"].update(undersupplied_below=2.0))
    assert "undersupplied_below must be smaller than oversupplied_above" in load_error(config_dir)


def test_values_outside_their_range_are_rejected(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["supply"].update(default_completion_rate=1.8))
    message = load_error(config_dir)
    assert "supply.default_completion_rate" in message
    assert "less than or equal to 1" in message


def test_unknown_key_is_rejected(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["demand"]["weights"].update(postngs=0.1))
    message = load_error(config_dir)
    assert "demand.weights.postngs: unknown key" in message


def test_missing_key_is_rejected(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["supply"].pop("default_completion_rate"))
    assert "supply.default_completion_rate: required key is missing" in load_error(config_dir)


def test_missing_file_fails_clearly(config_dir):
    (config_dir / "sectors.yaml").unlink()
    assert "Missing configuration file" in load_error(config_dir)
    assert "sectors.yaml" in load_error(config_dir)


def test_broken_yaml_reports_the_line(config_dir):
    (config_dir / "scope.yaml").write_text("state: Maharashtra\ndistricts: [MH-PUNE\n", "utf-8")
    message = load_error(config_dir)
    assert "scope.yaml is not valid YAML" in message
    assert "line" in message


def test_every_broken_file_is_reported_at_once(config_dir):
    edit(config_dir, "scoring.yaml", lambda d: d["mismatch"].update(oversupplied_above=0.1))
    edit(config_dir, "scope.yaml", lambda d: d.update(golden_path_district="MH-THANE"))
    message = load_error(config_dir)
    assert "scoring.yaml" in message and "scope.yaml" in message


def test_external_trend_route_needs_a_threshold_before_enabling(config_dir):
    edit(
        config_dir,
        "scoring.yaml",
        lambda d: d["trend"]["emerging"]["external_trend"].update(enabled=True),
    )
    assert "min_signal_value is null" in load_error(config_dir)


def test_unsupported_language_is_rejected(config_dir):
    edit(config_dir, "scope.yaml", lambda d: d["languages"].update(candidate_ui=["en", "ta"]))
    assert "languages.candidate_ui" in load_error(config_dir)


def test_api_key_cannot_be_written_in_yaml(config_dir):
    edit(config_dir, "llm.yaml", lambda d: d["llm"].update(api_key="sk-secret"))
    assert "llm.api_key: unknown key" in load_error(config_dir)


# ---------------------------------------------------------------- cross-file rules
def test_planted_pattern_must_use_known_districts_and_sectors(config_dir):
    def change(d):
        d["planted_patterns"]["PP1"]["districts"].append("MH-THANE")
        d["planted_patterns"]["PP1"]["sectors"].append("TEXTILES")

    edit(config_dir, "synthetic.yaml", change)
    message = load_error(config_dir)
    assert "'MH-THANE' is not a district in scope.yaml" in message
    assert "'TEXTILES' is not a sector in sectors.yaml" in message


def test_synthetic_history_must_cover_the_forecast_window(config_dir):
    edit(config_dir, "synthetic.yaml", lambda d: d["history"].update(start_quarter="2026Q1"))
    assert "history covers 3 quarters" in load_error(config_dir)


def test_embedding_dimension_must_match_the_database(config_dir):
    edit(config_dir, "llm.yaml", lambda d: d["embeddings"].update(dimension=768))
    assert "database stores 384-number vectors" in load_error(config_dir)


def test_live_cloud_llm_needs_an_api_key_from_the_environment(config_dir):
    edit(config_dir, "llm.yaml", lambda d: d["llm"].update(provider="anthropic", mode="live"))
    assert "Set LLM_API_KEY in .env" in load_error(config_dir)

    config = load_config(config_dir, settings(llm_api_key="test-key"))
    assert config.llm.llm.active_model == "claude-opus-5"


# ---------------------------------------------------------------- environment overrides
def test_environment_overrides_replace_yaml_values(config_dir):
    config = load_config(
        config_dir,
        settings(
            llm_provider="mock",
            llm_mode="cache_only",
            embeddings_enabled=True,
            embedding_model_path="D:/models/e5",
            synth_seed=7,
        ),
    )
    assert (config.llm.llm.provider, config.llm.llm.mode) == ("mock", "cache_only")
    assert config.llm.embeddings.enabled is True
    assert config.llm.embeddings.local_path == "D:/models/e5"
    assert config.synthetic.seed == 7
    assert set(config.overrides) == {
        "LLM_PROVIDER",
        "LLM_MODE",
        "EMBEDDINGS_ENABLED",
        "EMBEDDING_MODEL_PATH",
        "SYNTH_SEED",
    }


def test_overrides_are_read_from_real_environment_variables(config_dir, monkeypatch):
    monkeypatch.setenv("SYNTH_SEED", "42")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_MODEL", "some-local-model")
    config = load_config(config_dir, Settings(_env_file=None))
    assert config.synthetic.seed == 42
    assert config.llm.llm.active_model == "some-local-model"


def test_overrides_are_validated_too(config_dir):
    assert "llm.provider" in load_error(config_dir, llm_provider="chatbot-9000")
    # A live provider without a model is refused.
    assert "has no model" in load_error(config_dir, llm_provider="openai", llm_mode="live")


def test_env_example_template_sets_no_overrides():
    # Empty "KEY=" lines must mean "not set" (a comment on the same line would become the value).
    template = Settings(_env_file=REPO_ROOT / ".env.example")
    names = [name.lower() for name in OVERRIDE_VARIABLES if name != "CONFIG_DIR"]
    assert {name: getattr(template, name) for name in names} == dict.fromkeys(names)
    assert template.config_dir == REAL_CONFIG_DIR


def test_llm_model_without_a_model_provider_is_refused(config_dir):
    assert "does not use a model" in load_error(config_dir, llm_model="anything")


# ---------------------------------------------------------------- small details
def test_bare_yaml_off_means_off(config_dir):
    path = config_dir / "llm.yaml"
    path.write_text(path.read_text("utf-8").replace('mode: "live"', "mode: off"), "utf-8")
    assert load_config(config_dir, settings()).llm.llm.mode == "off"


def test_repeated_yaml_keys_are_refused(config_dir):
    path = config_dir / "scoring.yaml"
    path.write_text(path.read_text("utf-8") + "\nversion: v99\n", "utf-8")
    assert "key 'version' appears twice" in load_error(config_dir)


def test_scoring_hash_is_the_same_on_windows_and_linux(config_dir):
    path = config_dir / "scoring.yaml"
    lf_hash = scoring_file_sha256(path)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert scoring_file_sha256(path) == lf_hash


def test_configuration_is_read_only():
    config = load_config(settings=settings())
    with pytest.raises(Exception, match="frozen"):
        config.scoring.mismatch.undersupplied_below = 0.1  # type: ignore[misc]
