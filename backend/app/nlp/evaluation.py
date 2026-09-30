"""Measure the skill matcher on a hand-made evaluation set
(data/gold/skill_matching_cases.yaml): a small synthetic vocabulary plus phrases with the
skill each SHOULD match.

Outcome labels per case:
  correct accept / correct review   right skill (accepted automatically / sent to review)
  wrong                             a DIFFERENT skill was assigned (accept or review)
  missed                            no match although a skill was expected
  rejected                          unrelated phrase correctly matched nothing
  false review / false accept       unrelated phrase got a skill (review / accept)
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.core.settings import REPO_ROOT
from app.models import Skill, SkillAlias
from app.nlp.skill_matcher import MatchResult, SkillMatcher
from app.nlp.text import normalize_text

DEFAULT_CASES_FILE = REPO_ROOT / "data" / "gold" / "skill_matching_cases.yaml"
CATEGORIES = ("exact", "alias", "spelling", "semantic", "unrelated")


@dataclass(frozen=True)
class EvalCase:
    input: str
    expected: str | None
    category: str


@dataclass(frozen=True)
class Outcome:
    case: EvalCase
    result: MatchResult

    @property
    def predicted(self) -> str | None:
        skill = self.result.matched_skill
        return skill.code if skill else None

    @property
    def label(self) -> str:
        decision = self.result.decision
        if self.case.expected is None:
            return {"no_match": "rejected", "review": "false review", "accept": "false accept"}[
                decision
            ]
        if decision == "no_match":
            return "missed"
        if self.predicted != self.case.expected:
            return "wrong"
        return f"correct {decision}"


def load_eval_set(path: Path = DEFAULT_CASES_FILE) -> tuple[list[dict[str, Any]], list[EvalCase]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [EvalCase(c["input"], c["expected"], c["category"]) for c in data["cases"]]
    return data["vocabulary"], cases


def seed_vocabulary(db: Session, vocabulary: list[dict[str, Any]], source_ref: str) -> None:
    """Insert the evaluation vocabulary (marked synthetic, source "EVAL"). Does not commit."""
    provenance = {"source": "EVAL", "source_ref": source_ref, "is_synthetic": True}
    for entry in vocabulary:
        skill = Skill(
            code=entry["code"], name=entry["name"], skill_type=entry["skill_type"], **provenance
        )
        skill.aliases = [
            SkillAlias(
                alias=alias["text"],
                alias_normalized=normalize_text(alias["text"]),
                language=alias["language"],
                **provenance,
            )
            for alias in entry["aliases"]
        ]
        db.add(skill)
    db.flush()


def evaluate(matcher: SkillMatcher, cases: list[EvalCase]) -> list[Outcome]:
    results = matcher.match_many([case.input for case in cases])
    return [Outcome(case, result) for case, result in zip(cases, results, strict=True)]


def summarize(outcomes: list[Outcome]) -> dict[str, Any]:
    per_category = {
        category: Counter(o.label for o in outcomes if o.case.category == category)
        for category in CATEGORIES
    }
    accepts = [o for o in outcomes if o.result.decision == "accept"]
    correct_accepts = sum(1 for o in accepts if o.label == "correct accept")
    expected = [o for o in outcomes if o.case.expected is not None]
    found = sum(1 for o in expected if o.label.startswith("correct"))
    return {
        "per_category": per_category,
        "accept_precision": correct_accepts / len(accepts) if accepts else None,
        "found_rate": found / len(expected) if expected else None,
        "wrong": sum(1 for o in outcomes if o.label == "wrong"),
        "unrelated_false_accepts": per_category["unrelated"]["false accept"],
        "unrelated_false_reviews": per_category["unrelated"]["false review"],
        "methods": Counter(o.result.method for o in outcomes),
    }


def format_report(outcomes: list[Outcome], title: str) -> str:
    summary = summarize(outcomes)
    lines = [f"## {title}", "", "| Category | Cases | Outcomes |", "|---|---|---|"]
    for category, counts in summary["per_category"].items():
        total = sum(counts.values())
        detail = ", ".join(f"{label} {n}" for label, n in sorted(counts.items()))
        lines.append(f"| {category} | {total} | {detail} |")
    precision = summary["accept_precision"]
    lines += [
        "",
        f"- Right skill found (accepted or sent to review): **{summary['found_rate']:.0%}** "
        "of phrases that have a matching skill",
        (
            f"- Precision of automatic accepts: **{precision:.0%}**"
            if precision is not None
            else "- No automatic accepts"
        ),
        f"- Wrong skill assigned: **{summary['wrong']}**; unrelated phrases falsely accepted: "
        f"**{summary['unrelated_false_accepts']}**, sent to review: "
        f"**{summary['unrelated_false_reviews']}**",
        "- Methods used: " + ", ".join(f"{m} {n}" for m, n in sorted(summary["methods"].items())),
        "",
        "| Input | Expected | Result | Method | Confidence | Outcome |",
        "|---|---|---|---|---|---|",
    ]
    for o in outcomes:
        r = o.result
        shown = r.matched_skill.name if r.matched_skill else "-"
        lines.append(
            f"| {o.case.input.strip()} | {o.case.expected or '(none)'} | {shown} | {r.method} "
            f"| {r.confidence:.2f} | {o.label} |"
        )
    return "\n".join(lines)
