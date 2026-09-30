"""LLM providers behind the common LLMClient interface.

    mock       deterministic rules, no network, no key, Rs 0 (the default; used by tests)
    ollama     a local model through the Ollama HTTP API (free; needs Ollama running)
    anthropic  Claude through the official `anthropic` SDK   (pip install anthropic)
    openai     OpenAI through the official `openai` SDK       (pip install openai)

The cloud SDKs are optional and imported only when that provider is chosen. API keys come
from the LLM_API_KEY environment variable (.env), never from config files or code.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import ProductConfig
from app.core.settings import Settings, get_settings
from app.llm.client import LlmCallError, LLMClient, LlmTask
from app.nlp.text import normalize_text

MOCK_MODEL = "mock-rules-v1"
_STOP_WORDS = {"and", "or", "the", "of", "for", "with", "in", "on", "a", "an", "to"}


def _words(text: str) -> set[str]:
    return {w for w in normalize_text(text).split() if w not in _STOP_WORDS and len(w) > 1}


# --------------------------------------------------------------------------- mock
@dataclass
class MockLLMClient(LLMClient):
    """A stand-in LLM that answers with simple, documented rules (never with made-up facts):

    skill_match_fallback / role_match_fallback: the candidate sharing the most words with the
        phrase (or title + text); null if none shares a word.
    skill_phrase_extraction: short comma/"and"-separated chunks of the text, quoted verbatim.

    Tests can script answers per task: `responses={"skill_match_fallback": "not json"}` or an
    exception instance (raised) or a callable(payload) -> str.
    """

    responses: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.provider, self.model = "mock", MOCK_MODEL

    def _complete(
        self, task: LlmTask[Any], payload: dict[str, Any], system: str, user: str, timeout: float
    ) -> str:
        scripted = (self.responses or {}).get(task.name)
        if isinstance(scripted, BaseException):
            raise scripted
        if callable(scripted):
            return scripted(payload)
        if isinstance(scripted, str):
            return scripted
        if task.name == "skill_match_fallback":
            code, shared = self._closest(payload["phrase"], payload["candidates"], "name")
            return json.dumps({"skill_code": code, "reason": self._reason(shared)})
        if task.name == "role_match_fallback":
            text = f"{payload['title']} {payload.get('text') or ''}"
            code, shared = self._closest(text, payload["candidates"], "title")
            return json.dumps({"role_code": code, "reason": self._reason(shared)})
        if task.name == "skill_phrase_extraction":
            return json.dumps({"phrases": self._chunks(payload["text"])}, ensure_ascii=False)
        raise LlmCallError(f"the mock does not know the task '{task.name}'")

    @staticmethod
    def _closest(
        text: str, candidates: list[dict[str, str]], field: str
    ) -> tuple[str | None, set[str]]:
        words = _words(text)
        best, best_shared = None, set()
        for candidate in candidates:  # candidates arrive best-first; ties keep the first
            shared = words & _words(candidate[field])
            if len(shared) > len(best_shared):
                best, best_shared = candidate["code"], shared
        return best, best_shared

    @staticmethod
    def _reason(shared: set[str]) -> str:
        if not shared:
            return "mock rule: no candidate shares a word with the input"
        return f"mock rule: shares the words {', '.join(sorted(shared))}"

    @staticmethod
    def _chunks(text: str) -> list[str]:
        parts = re.split(r"[,;:.\n।|]| and | with | और | आणि ", text)
        chunks = []
        for part in parts:
            part = part.strip()
            words = part.split()
            if 1 <= len(words) <= 4 and not re.search(r"\d", part) and normalize_text(part):
                chunks.append(part)
        return chunks[:10]


# --------------------------------------------------------------------------- ollama
@dataclass
class OllamaLLMClient(LLMClient):
    """A local model served by Ollama (https://ollama.com), via POST /api/chat with a JSON
    schema in `format` (structured output). No key, no cost; the model must be pulled first
    (`ollama pull <model>`) and named in config/llm.yaml models.ollama."""

    base_url: str = "http://127.0.0.1:11434"
    opener: Callable[..., Any] = urllib.request.urlopen  # replaced in tests

    def __post_init__(self) -> None:
        self.provider, self.model = "ollama", self.settings.active_model or ""

    def _complete(
        self, task: LlmTask[Any], payload: dict[str, Any], system: str, user: str, timeout: float
    ) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": task.json_schema,
            "options": {"temperature": 0},
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                answer = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LlmCallError(f"Ollama answered HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc):
                raise TimeoutError(f"Ollama did not answer within {timeout}s") from None
            raise LlmCallError(f"cannot reach Ollama at {self.base_url} ({exc})") from None
        except json.JSONDecodeError:
            raise LlmCallError("Ollama sent a response that is not JSON") from None
        try:
            return answer["message"]["content"]
        except (KeyError, TypeError):
            raise LlmCallError("unexpected Ollama response shape") from None


# --------------------------------------------------------------------------- anthropic
@dataclass
class AnthropicLLMClient(LLMClient):
    """Claude via the official SDK with structured output (output_config json_schema).
    Retries are done by LLMClient (the SDK's own retries are switched off)."""

    api_key: str | None = None
    sdk_client: Any = None  # injected in tests; otherwise created from the SDK

    def __post_init__(self) -> None:
        self.provider, self.model = "anthropic", self.settings.active_model or ""

    def _client(self, timeout: float) -> Any:
        if self.sdk_client is None:
            try:
                import anthropic
            except ImportError:
                raise LlmCallError(
                    "the 'anthropic' package is not installed (pip install anthropic)"
                ) from None
            self.sdk_client = anthropic.Anthropic(
                api_key=self.api_key, timeout=timeout, max_retries=0
            )
        return self.sdk_client

    def _complete(
        self, task: LlmTask[Any], payload: dict[str, Any], system: str, user: str, timeout: float
    ) -> str:
        client = self._client(timeout)
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.settings.max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": task.json_schema}},
            )
        except Exception as exc:  # SDK errors (timeout, connection, HTTP status ...)
            if "timeout" in type(exc).__name__.lower():
                raise TimeoutError(f"no answer within {timeout}s") from None
            raise LlmCallError(f"{type(exc).__name__}: {exc}") from None
        if response.stop_reason == "refusal":
            raise LlmCallError("the model refused to answer")
        if response.stop_reason == "max_tokens":
            raise LlmCallError("the answer was cut off (max_output_tokens too small)")
        for block in response.content:
            if block.type == "text":
                return block.text
        raise LlmCallError("the answer contained no text")


# --------------------------------------------------------------------------- openai
@dataclass
class OpenAILLMClient(LLMClient):
    """OpenAI via the official SDK with structured output (json_schema, strict)."""

    api_key: str | None = None
    sdk_client: Any = None

    def __post_init__(self) -> None:
        self.provider, self.model = "openai", self.settings.active_model or ""

    def _client(self, timeout: float) -> Any:
        if self.sdk_client is None:
            try:
                import openai
            except ImportError:
                raise LlmCallError(
                    "the 'openai' package is not installed (pip install openai)"
                ) from None
            self.sdk_client = openai.OpenAI(api_key=self.api_key, timeout=timeout, max_retries=0)
        return self.sdk_client

    def _complete(
        self, task: LlmTask[Any], payload: dict[str, Any], system: str, user: str, timeout: float
    ) -> str:
        client = self._client(timeout)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": task.name, "schema": task.json_schema, "strict": True},
                },
            )
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower():
                raise TimeoutError(f"no answer within {timeout}s") from None
            raise LlmCallError(f"{type(exc).__name__}: {exc}") from None
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise LlmCallError("the model refused to answer")
        if not message.content:
            raise LlmCallError("the answer contained no text")
        return message.content


# --------------------------------------------------------------------------- factory
def create_llm_client(
    config: ProductConfig,
    db: Session | None = None,
    settings: Settings | None = None,
    **overrides: Any,
) -> LLMClient | None:
    """The configured client, or None when the LLM is switched off (provider none / mode off).
    `overrides` are passed to the client (tests use them, e.g. responses=... for the mock)."""
    llm = config.llm.llm
    if llm.provider == "none" or llm.mode == "off":
        return None
    settings = settings or get_settings()
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if llm.provider == "mock":
        return MockLLMClient(llm, db=db, **overrides)
    if llm.provider == "ollama":
        return OllamaLLMClient(llm, db=db, base_url=llm.ollama_base_url, **overrides)
    if llm.provider == "anthropic":
        return AnthropicLLMClient(llm, db=db, api_key=key, **overrides)
    return OpenAILLMClient(llm, db=db, api_key=key, **overrides)
