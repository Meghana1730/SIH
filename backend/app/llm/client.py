"""LLM access with guard rails (docs/04-architecture.md §4.6-4.7).

    client = create_llm_client(config, db=db)            # None when the LLM is switched off
    result = client.run(SKILL_MATCH_FALLBACK, payload)    # never raises for LLM problems
    if result.ok: use(result.output)                      # a validated Pydantic object

Every call goes through the same steps:
  1. switched off / task disabled         -> ok=False ("off"), nothing is called
  2. cache (llm_cache table)              -> the stored answer, re-validated (cache_hit=True)
  3. mode cache_only and not cached       -> ok=False, nothing is called
  4. budget (llm.max_calls_per_job)       -> ok=False once the budget is used up
  5. provider call with a timeout; retries on errors, invalid JSON or invalid output
  6. JSON parse -> schema validation (Pydantic) -> grounding check (the task's own rules,
     e.g. "the chosen skill must be one of the candidates", "phrases must be quoted from the
     input", "no URLs", "no numbers that are not in the input")
  7. store the validated answer in the cache, return it with provenance

The LLM only interprets the evidence it is given. Tasks are designed so an answer can only
choose among given candidates or quote the given text; anything else fails validation.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config.llm import LlmSettings
from app.models import LlmCache

T = TypeVar("T", bound=BaseModel)


class LlmCallError(Exception):
    """The provider could not answer (timeout, network, HTTP error, refusal)."""


class LlmOutputError(Exception):
    """The answer is not usable (not JSON, wrong shape, or not grounded in the input)."""


@dataclass(frozen=True)
class LlmTask(Generic[T]):
    """One kind of question we may ask an LLM.

    name        : key in config/llm.yaml `llm.tasks` (enabled flag + prompt_version)
    system      : fixed instructions (rules against inventing facts)
    json_schema : the answer's JSON schema, sent to providers that support structured output
    output_model: Pydantic model that validates the answer
    render      : payload -> user message
    check       : (payload, answer) -> problems; any problem makes the answer invalid
    """

    name: str
    system: str
    json_schema: dict[str, Any]
    output_model: type[T]
    render: Callable[[dict[str, Any]], str]
    check: Callable[[dict[str, Any], T], list[str]]


@dataclass(frozen=True)
class LlmResult(Generic[T]):
    ok: bool
    output: T | None
    error: str | None
    task: str
    prompt_version: str
    provider: str
    model: str
    cache_hit: bool
    attempts: int
    generated_at: datetime | None
    input_sha256: str

    def provenance(self) -> dict[str, Any]:
        """Stored next to anything derived from this answer."""
        return {
            "task": self.task,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "model": self.model,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "cache_hit": self.cache_hit,
            "attempts": self.attempts,
            "input_sha256": self.input_sha256,
            "ok": self.ok,
            **({"error": self.error} if self.error else {}),
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class LLMClient(ABC):
    """Base class of every provider. Subclasses implement `_complete` only."""

    settings: LlmSettings
    db: Session | None = None  # for the llm_cache table; None = no caching
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    calls: int = 0  # live provider calls made by this client (the budget counter)

    provider: str = field(init=False, default="")
    model: str = field(init=False, default="")

    @abstractmethod
    def _complete(
        self, task: LlmTask[Any], payload: dict[str, Any], system: str, user: str, timeout: float
    ) -> str:
        """Return the provider's raw text answer (expected to be JSON)."""

    # ------------------------------------------------------------------ public
    def run(self, task: LlmTask[T], payload: dict[str, Any]) -> LlmResult[T]:
        settings = self.settings
        task_settings = getattr(settings.tasks, task.name)
        prompt_version = task_settings.prompt_version
        input_hash = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

        def result(
            ok: bool,
            output: T | None = None,
            error: str | None = None,
            *,
            cache_hit: bool = False,
            attempts: int = 0,
            generated_at: datetime | None = None,
        ) -> LlmResult[T]:
            return LlmResult(
                ok,
                output,
                error,
                task.name,
                prompt_version,
                self.provider,
                self.model,
                cache_hit,
                attempts,
                generated_at,
                input_hash,
            )

        if settings.mode == "off":
            return result(False, error="LLM is switched off (config/llm.yaml mode: off)")
        if not task_settings.enabled:
            return result(False, error=f"LLM task '{task.name}' is disabled in config/llm.yaml")

        key = self.cache_key(task, prompt_version, payload)
        cached = self._cache_get(key)
        if cached is not None:
            try:
                output = self._validate(task, payload, cached["output"])
                generated = datetime.fromisoformat(cached["generated_at"])
                return result(True, output, cache_hit=True, generated_at=generated)
            except (LlmOutputError, KeyError, ValueError):
                pass  # an old answer that no longer validates: ask again (if allowed)
        if settings.mode == "cache_only":
            return result(False, error="not in the LLM cache (mode cache_only)")

        system, user = task.system, task.render(payload)
        attempts, last_error = 0, "no attempt made"
        for attempt in range(settings.retries + 1):
            if self.calls >= settings.max_calls_per_job:
                return result(
                    False,
                    error=f"LLM budget used up ({settings.max_calls_per_job} calls per job)",
                    attempts=attempts,
                )
            if attempt > 0:
                self.sleep(settings.retry_backoff_seconds * (2 ** (attempt - 1)))
            attempts += 1
            self.calls += 1
            try:
                raw = self._complete(task, payload, system, user, settings.timeout_seconds)
                output = self._validate(task, payload, self._parse(raw))
            except LlmCallError as exc:
                last_error = f"provider error: {exc}"
                continue
            except LlmOutputError as exc:
                last_error = f"invalid answer: {exc}"
                continue
            except TimeoutError as exc:
                last_error = f"timeout: {exc or 'no answer in time'}"
                continue
            generated_at = self.clock()
            self._cache_put(key, task, prompt_version, output, generated_at)
            return result(True, output, attempts=attempts, generated_at=generated_at)
        return result(False, error=last_error, attempts=attempts)

    def cache_key(self, task: LlmTask[Any], prompt_version: str, payload: dict[str, Any]) -> str:
        material = {
            "provider": self.provider,
            "model": self.model,
            "task": task.name,
            "prompt_version": prompt_version,
            "schema": task.json_schema,
            "input": payload,
        }
        return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _parse(raw: str) -> Any:
        text = (raw or "").strip()
        if text.startswith("```"):  # some local models wrap JSON in a code fence
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LlmOutputError(f"not valid JSON ({exc.msg})") from None

    @staticmethod
    def _validate(task: LlmTask[T], payload: dict[str, Any], data: Any) -> T:
        try:
            output = task.output_model.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "(answer)"
            raise LlmOutputError(f"does not match the schema: {where}: {first['msg']}") from None
        problems = task.check(payload, output)
        if problems:
            raise LlmOutputError("; ".join(problems))
        return output

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        if self.db is None:
            return None
        entry = self.db.get(LlmCache, key)
        if entry is None:
            return None
        entry.last_used_at = self.clock()
        return entry.response_json

    def _cache_put(
        self,
        key: str,
        task: LlmTask[Any],
        prompt_version: str,
        output: BaseModel,
        generated_at: datetime,
    ) -> None:
        if self.db is None:
            return
        self.db.merge(
            LlmCache(
                cache_key=key,
                provider=self.provider,
                model=self.model,
                task=task.name,
                prompt_version=prompt_version,
                response_json={
                    "output": output.model_dump(mode="json"),
                    "generated_at": generated_at.isoformat(),
                },
                last_used_at=generated_at,
            )
        )
        self.db.flush()
