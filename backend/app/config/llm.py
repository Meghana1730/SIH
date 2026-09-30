"""Models for config/llm.yaml (optional LLM provider and embedding model)."""

from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.config.base import ConfigModel, Text

ProviderName = Literal["none", "mock", "ollama", "openai", "anthropic"]
LlmMode = Literal["off", "cache_only", "live"]
PromptVersion = Annotated[str, StringConstraints(pattern=r"^v[0-9]+$")]

# Providers that call a real model and therefore need a model name.
MODEL_PROVIDERS = ("ollama", "openai", "anthropic")
# Cloud providers that also need LLM_API_KEY (checked by the loader, which sees .env).
KEYED_PROVIDERS = ("openai", "anthropic")


class ProviderModels(ConfigModel):
    ollama: Text | None
    openai: Text | None
    anthropic: Text | None


class LlmTask(ConfigModel):
    enabled: bool
    prompt_version: PromptVersion


class LlmTasks(ConfigModel):
    skill_phrase_extraction: LlmTask
    skill_match_fallback: LlmTask
    role_match_fallback: LlmTask
    module_outline_polish: LlmTask
    consultation_insights: LlmTask
    chat_intent_parsing: LlmTask
    explanation_paraphrase: LlmTask


class LlmSettings(ConfigModel):
    provider: ProviderName
    mode: LlmMode
    timeout_seconds: Annotated[float, Field(gt=0, le=120)]
    retries: Annotated[int, Field(ge=0, le=3)]
    retry_backoff_seconds: Annotated[float, Field(ge=0, le=60)]
    max_calls_per_job: Annotated[int, Field(ge=0)]
    max_output_tokens: Annotated[int, Field(ge=16, le=16000)]
    models: ProviderModels
    ollama_base_url: Annotated[str, StringConstraints(pattern=r"^https?://\S+$")]
    tasks: LlmTasks

    @field_validator("mode", mode="before")
    @classmethod
    def _yaml_off_is_false(cls, value: Any) -> Any:
        # YAML reads a bare `off` as the boolean False; treat it as "off".
        return "off" if value is False else value

    @model_validator(mode="after")
    def _usable(self) -> Self:
        if self.mode == "off":
            return self
        if self.provider == "none":
            raise ValueError(f"mode '{self.mode}' needs a provider, but provider is 'none'")
        if self.provider in MODEL_PROVIDERS and not self.active_model:
            raise ValueError(
                f"provider '{self.provider}' has no model: set models.{self.provider} "
                "(or the LLM_MODEL environment variable)"
            )
        return self

    @property
    def active_model(self) -> str | None:
        if self.provider in MODEL_PROVIDERS:
            return getattr(self.models, self.provider)
        return None


class EmbeddingSettings(ConfigModel):
    enabled: bool
    model_name: Text
    dimension: Annotated[int, Field(ge=1)]
    local_path: Text  # relative to the repository root
    query_prefix: str
    document_prefix: str
    batch_size: Annotated[int, Field(ge=1, le=1024)]
    # Cosine similarity at or below this value counts as confidence 0; 1.0 counts as 1.
    # Model-specific: some models score even unrelated phrases fairly high.
    similarity_floor: Annotated[float, Field(ge=0, lt=1)]


class LlmConfig(ConfigModel):
    llm: LlmSettings
    embeddings: EmbeddingSettings
