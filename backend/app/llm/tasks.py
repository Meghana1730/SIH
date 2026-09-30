"""The questions KaushalSetu may ask an LLM, with their prompts, answer schemas and grounding
checks. Each task can only CHOOSE among given candidates or QUOTE the given text, so an LLM
answer can never introduce a skill, role, number, code or URL that is not in the evidence.

Change a prompt? Bump the task's prompt_version in config/llm.yaml (old cached answers are
then ignored).
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.llm.client import LlmTask
from app.nlp.text import normalize_text

RULES = (
    "You help a labour-market analysis tool for skilling in India. Use ONLY the information "
    "in the input JSON. Never invent or estimate statistics, job counts, salaries, employer "
    "claims, placement numbers, government codes (NCO, NSQF, QP, NOS, LGD, DGT or any other) "
    "or URLs. If the input does not support an answer, answer null. Reply with one JSON object "
    "that matches the requested schema exactly, with no other text."
)

_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

Reason = Annotated[str, StringConstraints(max_length=300)]


def _answer_text_problems(text: str, payload: dict[str, Any]) -> list[str]:
    """Free text in an answer may not add URLs or numbers that the input does not contain."""
    problems = []
    if _URL.search(text):
        problems.append("the answer contains a URL")
    source = json.dumps(payload, ensure_ascii=False)
    invented = sorted({n for n in _NUMBER.findall(text) if n not in source})
    if invented:
        problems.append(f"the answer contains numbers not in the input: {invented}")
    return problems


# --------------------------------------------------------------------------- choose a skill
class SkillChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_code: str | None
    reason: Reason


def _check_skill_choice(payload: dict[str, Any], answer: SkillChoice) -> list[str]:
    problems = _answer_text_problems(answer.reason, payload)
    codes = {c["code"] for c in payload["candidates"]}
    if answer.skill_code is not None and answer.skill_code not in codes:
        problems.append(f"'{answer.skill_code}' is not one of the candidate skills")
    return problems


SKILL_MATCH_FALLBACK: LlmTask[SkillChoice] = LlmTask(
    name="skill_match_fallback",
    system=RULES + " Task: a phrase from a job advertisement could not be matched to a skill with "
    "certainty. Choose the ONE candidate skill the phrase refers to, or null if none of them "
    "fits. You may only answer with a code from the candidate list.",
    json_schema={
        "type": "object",
        "properties": {
            "skill_code": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "reason": {"type": "string"},
        },
        "required": ["skill_code", "reason"],
        "additionalProperties": False,
    },
    output_model=SkillChoice,
    render=lambda payload: json.dumps(payload, ensure_ascii=False),
    check=_check_skill_choice,
)


# --------------------------------------------------------------------------- choose a role
class RoleChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_code: str | None
    reason: Reason


def _check_role_choice(payload: dict[str, Any], answer: RoleChoice) -> list[str]:
    problems = _answer_text_problems(answer.reason, payload)
    codes = {c["code"] for c in payload["candidates"]}
    if answer.role_code is not None and answer.role_code not in codes:
        problems.append(f"'{answer.role_code}' is not one of the candidate roles")
    return problems


ROLE_MATCH_FALLBACK: LlmTask[RoleChoice] = LlmTask(
    name="role_match_fallback",
    system=RULES
    + " Task: decide which ONE of the candidate job roles a job advertisement is for, or "
    "null if none fits. You may only answer with a code from the candidate list.",
    json_schema={
        "type": "object",
        "properties": {
            "role_code": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "reason": {"type": "string"},
        },
        "required": ["role_code", "reason"],
        "additionalProperties": False,
    },
    output_model=RoleChoice,
    render=lambda payload: json.dumps(payload, ensure_ascii=False),
    check=_check_role_choice,
)


# --------------------------------------------------------------------------- quote phrases
class SkillPhrases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phrases: Annotated[
        list[Annotated[str, StringConstraints(max_length=120)]], Field(max_length=20)
    ]


def _check_phrases(payload: dict[str, Any], answer: SkillPhrases) -> list[str]:
    source = f" {normalize_text(payload['text'])} "
    ungrounded = [p for p in answer.phrases if f" {normalize_text(p)} " not in source]
    empty = [p for p in answer.phrases if not normalize_text(p)]
    problems = []
    if ungrounded:
        problems.append(f"phrases not quoted from the text: {ungrounded[:3]}")
    if empty:
        problems.append("empty phrases")
    return problems


SKILL_PHRASE_EXTRACTION: LlmTask[SkillPhrases] = LlmTask(
    name="skill_phrase_extraction",
    system=RULES
    + " Task: list the short phrases in the job advertisement text that name a skill, tool or "
    "type of work the job needs. Copy each phrase EXACTLY as it appears in the text (same "
    "words, same language); do not translate, summarise or add anything. At most 20 phrases; "
    "an empty list if there are none.",
    json_schema={
        "type": "object",
        "properties": {"phrases": {"type": "array", "items": {"type": "string"}}},
        "required": ["phrases"],
        "additionalProperties": False,
    },
    output_model=SkillPhrases,
    render=lambda payload: json.dumps(payload, ensure_ascii=False),
    check=_check_phrases,
)

TASKS = {t.name: t for t in (SKILL_MATCH_FALLBACK, ROLE_MATCH_FALLBACK, SKILL_PHRASE_EXTRACTION)}
