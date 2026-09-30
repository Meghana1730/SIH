"""Optional LLM layer: one interface (LLMClient), a free deterministic mock, and real
providers (Ollama, Anthropic, OpenAI). The product works fully without any real LLM.

    from app.llm import create_llm_client, SKILL_MATCH_FALLBACK
"""

from app.llm.client import LlmCallError, LLMClient, LlmOutputError, LlmResult, LlmTask
from app.llm.providers import (
    AnthropicLLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
    create_llm_client,
)
from app.llm.tasks import (
    ROLE_MATCH_FALLBACK,
    SKILL_MATCH_FALLBACK,
    SKILL_PHRASE_EXTRACTION,
    TASKS,
    RoleChoice,
    SkillChoice,
    SkillPhrases,
)

__all__ = [
    "ROLE_MATCH_FALLBACK",
    "SKILL_MATCH_FALLBACK",
    "SKILL_PHRASE_EXTRACTION",
    "TASKS",
    "AnthropicLLMClient",
    "LLMClient",
    "LlmCallError",
    "LlmOutputError",
    "LlmResult",
    "LlmTask",
    "MockLLMClient",
    "OllamaLLMClient",
    "OpenAILLMClient",
    "RoleChoice",
    "SkillChoice",
    "SkillPhrases",
    "create_llm_client",
]
