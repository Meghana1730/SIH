"""LLM layer tests: mock mode, validation, grounding, retries, failures, cache, budget, and
the real-provider adapters (with fake transports: no network, no key, no cost)."""

import dataclasses
import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

from app.config import load_config
from app.core.settings import Settings
from app.llm import (
    ROLE_MATCH_FALLBACK,
    SKILL_MATCH_FALLBACK,
    SKILL_PHRASE_EXTRACTION,
    AnthropicLLMClient,
    LlmCallError,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
    create_llm_client,
)

CANDIDATES = [
    {"code": "ev-diagnostics", "name": "EV Diagnostics"},
    {"code": "battery-management", "name": "Battery Management"},
]
SKILL_PAYLOAD = {
    "phrase": "battery pack checks",
    "context": "Battery pack checks.",
    "candidates": CANDIDATES,
}


@pytest.fixture(scope="module")
def config():
    return load_config(settings=Settings(_env_file=None))


@pytest.fixture
def settings(config):
    """The configured LLM settings, without waiting between retries."""
    return config.llm.llm.model_copy(update={"retry_backoff_seconds": 0.0})


def with_llm(config, **changes):
    llm = config.llm.llm.model_copy(update=changes)
    return dataclasses.replace(config, llm=config.llm.model_copy(update={"llm": llm}))


# ---------------------------------------------------------------- mock mode (the default)
def test_the_default_llm_is_the_free_mock(config):
    client = create_llm_client(config)
    assert isinstance(client, MockLLMClient)
    assert (client.provider, client.model) == ("mock", "mock-rules-v1")


def test_mock_answers_with_a_validated_candidate_and_provenance(settings):
    client = MockLLMClient(settings)
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert result.ok and result.output.skill_code == "battery-management"  # shares "battery"
    provenance = result.provenance()
    assert provenance["provider"] == "mock"
    assert provenance["prompt_version"] == settings.tasks.skill_match_fallback.prompt_version
    assert provenance["generated_at"] and len(provenance["input_sha256"]) == 64
    assert provenance["cache_hit"] is False and provenance["attempts"] == 1


def test_mock_says_null_when_nothing_fits(settings):
    payload = {**SKILL_PAYLOAD, "phrase": "walk-in interview"}
    result = MockLLMClient(settings).run(SKILL_MATCH_FALLBACK, payload)
    assert result.ok and result.output.skill_code is None


def test_mock_role_choice_and_phrase_quotes_are_grounded(settings):
    role = MockLLMClient(settings).run(
        ROLE_MATCH_FALLBACK,
        {
            "title": "Charging point fitter",
            "text": "installs chargers",
            "candidates": [{"code": "ev-charging-installer", "title": "EV Charging Technician"}],
        },
    )
    assert role.ok and role.output.role_code == "ev-charging-installer"  # shares "charging"
    enabled = settings.tasks.model_copy(
        update={
            "skill_phrase_extraction": settings.tasks.skill_phrase_extraction.model_copy(
                update={"enabled": True}
            )
        }
    )
    client = MockLLMClient(settings.model_copy(update={"tasks": enabled}))
    phrases = client.run(SKILL_PHRASE_EXTRACTION, {"text": "Need wiring, earthing and panel work."})
    assert phrases.ok and phrases.output.phrases == ["Need wiring", "earthing", "panel work"]


# ---------------------------------------------------------------- invalid answers
@pytest.mark.parametrize(
    "answer, reason",
    [
        ("not json at all", "not valid JSON"),
        ('{"skill_code": "ev-diagnostics"}', "does not match the schema"),
        ('{"skill_code": "made-up-skill", "reason": "x"}', "not one of the candidate skills"),
        ('{"skill_code": null, "reason": "see https://example.com"}', "contains a URL"),
        ('{"skill_code": null, "reason": "demand grew 42 percent"}', "numbers not in the input"),
        ('{"skill_code": null, "reason": "ok", "extra": 1}', "does not match the schema"),
    ],
)
def test_invalid_answers_are_rejected_after_retries(settings, answer, reason):
    client = MockLLMClient(settings, responses={"skill_match_fallback": answer})
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert not result.ok and result.output is None
    assert reason in result.error
    assert result.attempts == settings.retries + 1  # retried, then gave up gracefully


def test_phrases_must_be_quoted_from_the_text(settings):
    enabled = settings.tasks.model_copy(
        update={
            "skill_phrase_extraction": settings.tasks.skill_phrase_extraction.model_copy(
                update={"enabled": True}
            )
        }
    )
    client = MockLLMClient(
        settings.model_copy(update={"tasks": enabled}),
        responses={"skill_phrase_extraction": json.dumps({"phrases": ["PLC programming"]})},
    )
    result = client.run(SKILL_PHRASE_EXTRACTION, {"text": "House wiring work."})
    assert not result.ok and "not quoted from the text" in result.error


def test_code_fenced_json_is_accepted(settings):
    fenced = '```json\n{"skill_code": "ev-diagnostics", "reason": "EV fault finding"}\n```'
    result = MockLLMClient(settings, responses={"skill_match_fallback": fenced}).run(
        SKILL_MATCH_FALLBACK, SKILL_PAYLOAD
    )
    assert result.ok and result.output.skill_code == "ev-diagnostics"


# ---------------------------------------------------------------- failures
@pytest.mark.parametrize("failure", [TimeoutError("slow"), LlmCallError("HTTP 503")])
def test_provider_failures_are_graceful(settings, failure):
    sleeps = []
    client = MockLLMClient(
        settings.model_copy(update={"retry_backoff_seconds": 0.5}),
        responses={"skill_match_fallback": failure},
        sleep=sleeps.append,
    )
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert not result.ok and result.output is None
    assert (
        ("timeout" in result.error)
        if isinstance(failure, TimeoutError)
        else ("HTTP 503" in result.error)
    )
    assert sleeps == [0.5 * 2**i for i in range(settings.retries)]  # exponential backoff


def test_a_failure_then_a_good_answer_succeeds(settings):
    answers = iter(
        [LlmCallError("hiccup"), '{"skill_code": "ev-diagnostics", "reason": "fault finding"}']
    )

    def flaky(payload):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    result = MockLLMClient(
        settings.model_copy(update={"retries": 1}), responses={"skill_match_fallback": flaky}
    ).run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert result.ok and result.attempts == 2


# ---------------------------------------------------------------- switches and budget
def test_off_mode_and_disabled_tasks_never_call(config, settings):
    assert create_llm_client(with_llm(config, mode="off")) is None
    assert create_llm_client(with_llm(config, provider="none")) is None
    client = MockLLMClient(
        settings.model_copy(update={"mode": "off"}),
        responses={"skill_match_fallback": RuntimeError("called!")},
    )
    assert "switched off" in client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD).error
    # skill_phrase_extraction is disabled in config/llm.yaml
    result = MockLLMClient(settings).run(SKILL_PHRASE_EXTRACTION, {"text": "wiring"})
    assert not result.ok and "disabled" in result.error


def test_budget_stops_calls(settings):
    client = MockLLMClient(settings.model_copy(update={"max_calls_per_job": 2, "retries": 0}))
    results = [
        client.run(SKILL_MATCH_FALLBACK, {**SKILL_PAYLOAD, "phrase": f"battery {i}"})
        for i in range(3)
    ]
    assert [r.ok for r in results] == [True, True, False]
    assert "budget" in results[2].error and client.calls == 2


@pytest.mark.db
def test_answers_are_cached_and_cache_only_mode_uses_them(db_session, settings):
    first = MockLLMClient(settings, db=db_session).run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    offline = MockLLMClient(
        settings.model_copy(update={"mode": "cache_only"}),
        db=db_session,
        responses={"skill_match_fallback": RuntimeError("no calls")},
    )
    cached = offline.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert cached.ok and cached.cache_hit and offline.calls == 0
    assert cached.output == first.output and cached.generated_at == first.generated_at
    missing = offline.run(SKILL_MATCH_FALLBACK, {**SKILL_PAYLOAD, "phrase": "something else"})
    assert not missing.ok and "not in the LLM cache" in missing.error


# ---------------------------------------------------------------- real providers (fake transports)
def test_ollama_adapter_sends_the_schema_and_reads_the_answer(settings):
    sent = {}

    def opener(request, timeout):
        sent.update(url=request.full_url, body=json.loads(request.data), timeout=timeout)
        answer = {
            "message": {"content": '{"skill_code": "ev-diagnostics", "reason": "fault finding"}'}
        }
        return io.BytesIO(json.dumps(answer).encode())

    ollama = settings.model_copy(
        update={
            "provider": "ollama",
            "models": settings.models.model_copy(update={"ollama": "local-model"}),
        }
    )
    client = OllamaLLMClient(ollama, base_url="http://127.0.0.1:11434", opener=opener)
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert result.ok and result.model == "local-model"
    assert sent["url"].endswith("/api/chat") and sent["timeout"] == settings.timeout_seconds
    assert (
        sent["body"]["format"] == SKILL_MATCH_FALLBACK.json_schema
        and sent["body"]["stream"] is False
    )


def test_ollama_adapter_reports_an_unreachable_server(settings):
    def opener(request, timeout):
        raise urllib.error.URLError("connection refused")

    client = OllamaLLMClient(settings.model_copy(update={"retries": 0}), opener=opener)
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert not result.ok and "cannot reach Ollama" in result.error


class FakeAnthropic:
    def __init__(self, text=None, stop_reason="end_turn"):
        self.calls = []
        self.messages = self
        self.text, self.stop_reason = text, stop_reason

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=self.text)
        return SimpleNamespace(content=[block], stop_reason=self.stop_reason)


def test_anthropic_adapter_uses_structured_output(settings):
    sdk = FakeAnthropic('{"skill_code": "battery-management", "reason": "battery pack"}')
    anthropic = settings.model_copy(update={"provider": "anthropic"})
    result = AnthropicLLMClient(anthropic, api_key="test", sdk_client=sdk).run(
        SKILL_MATCH_FALLBACK, SKILL_PAYLOAD
    )
    assert result.ok and result.output.skill_code == "battery-management"
    call = sdk.calls[0]
    assert (
        call["model"] == settings.models.anthropic and call["system"] == SKILL_MATCH_FALLBACK.system
    )
    assert call["output_config"] == {
        "format": {"type": "json_schema", "schema": SKILL_MATCH_FALLBACK.json_schema}
    }


def test_anthropic_refusal_is_a_graceful_failure(settings):
    sdk = FakeAnthropic("{}", stop_reason="refusal")
    client = AnthropicLLMClient(
        settings.model_copy(update={"retries": 0}), api_key="test", sdk_client=sdk
    )
    result = client.run(SKILL_MATCH_FALLBACK, SKILL_PAYLOAD)
    assert not result.ok and "refused" in result.error


def test_openai_adapter_uses_a_strict_json_schema(settings):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content='{"skill_code": null, "reason": "no fit"}', refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    openai = settings.model_copy(
        update={
            "provider": "openai",
            "models": settings.models.model_copy(update={"openai": "some-model"}),
        }
    )
    result = OpenAILLMClient(openai, api_key="test", sdk_client=sdk).run(
        SKILL_MATCH_FALLBACK, SKILL_PAYLOAD
    )
    assert result.ok and result.output.skill_code is None
    schema = calls[0]["response_format"]["json_schema"]
    assert schema["strict"] is True and schema["schema"] == SKILL_MATCH_FALLBACK.json_schema


def test_every_task_forbids_invented_facts():
    for task in (SKILL_MATCH_FALLBACK, ROLE_MATCH_FALLBACK, SKILL_PHRASE_EXTRACTION):
        assert "Never invent" in task.system and "government codes" in task.system
        assert task.json_schema["additionalProperties"] is False
