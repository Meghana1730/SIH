"""Measure the job pipeline on hand-labelled examples (data/gold/job_postings_gold.yaml) and,
optionally, on the synthetic postings' generator ground truth.

Skill metrics are micro-averaged over (example, skill) pairs, for OBSERVED skills only:
  "accepted"         only skills the pipeline accepts automatically
  "accepted+review"  also the ones it sends to human review
`optional_skills` in a gold example are fine to find but not required (not counted either
way). INFERRED skills are reported separately (they are hints, not observations).
Role accuracy: the predicted role (accepted or review) equals the expected one; "no role"
is correct when none is expected.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import REPO_ROOT
from app.jobs.processing import JobIntelligence, PostingAnalysis
from app.models.enums import EvidenceKind, MatchDecision

GOLD_FILE = REPO_ROOT / "data" / "gold" / "job_postings_gold.yaml"


class GoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    categories: Annotated[list[str], Field(min_length=1)]
    language: str
    sector: str | None = None
    title: str
    description: str | None
    expected_skills: list[str]
    optional_skills: list[str] = []
    expected_role: str | None
    acceptable_roles: list[str] = []  # also defensible for an ambiguous ad
    note: str | None = None


class GoldFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    vocabulary: str
    cases: Annotated[list[GoldCase], Field(min_length=1)]


def load_gold(path: Path = GOLD_FILE) -> GoldFile:
    return GoldFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass
class CaseResult:
    case: GoldCase
    analysis: PostingAnalysis
    accepted: set[str]
    observed: set[str]
    inferred: set[str]
    role: str | None
    role_decision: str | None

    @property
    def expected(self) -> set[str]:
        return set(self.case.expected_skills)

    def scores(self, predicted: set[str]) -> tuple[int, int, int]:
        optional = set(self.case.optional_skills)
        return (
            len(predicted & self.expected),
            len(predicted - self.expected - optional),
            len(self.expected - predicted),
        )

    @property
    def role_correct(self) -> bool:
        return self.role == self.case.expected_role or (
            self.role is not None and self.role in self.case.acceptable_roles
        )


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, scores: tuple[int, int, int]) -> None:
        self.tp += scores[0]
        self.fp += scores[1]
        self.fn += scores[2]

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass
class EvalReport:
    title: str
    results: list[CaseResult]
    settings: dict[str, Any] = field(default_factory=dict)

    def counts(self, view: str, cases: list[CaseResult] | None = None) -> Counts:
        total = Counts()
        for r in cases if cases is not None else self.results:
            total.add(r.scores(r.accepted if view == "accepted" else r.observed))
        return total

    def role_accuracy(self, cases: list[CaseResult] | None = None) -> float:
        cases = cases if cases is not None else self.results
        return sum(r.role_correct for r in cases) / len(cases) if cases else 0.0

    def summary(self) -> dict[str, Any]:
        accepted, observed = self.counts("accepted"), self.counts("observed")
        inferred_total = sum(len(r.inferred) for r in self.results)
        inferred_right = sum(len(r.inferred & r.expected) for r in self.results)
        return {
            "examples": len(self.results),
            "accepted": _metrics(accepted),
            "accepted_or_review": _metrics(observed),
            "role_accuracy": round(self.role_accuracy(), 3),
            "inferred_skills": inferred_total,
            "inferred_that_were_expected": inferred_right,
        }


def _metrics(c: Counts) -> dict[str, Any]:
    return {
        "precision": round(c.precision, 3),
        "recall": round(c.recall, 3),
        "f1": round(c.f1, 3),
        "tp": c.tp,
        "fp": c.fp,
        "fn": c.fn,
    }


def run_case(intel: JobIntelligence, case: GoldCase) -> CaseResult:
    analysis = intel.analyze(case.title, case.description, case.sector)
    observed = [s for s in analysis.skills if s.evidence_kind == EvidenceKind.OBSERVED]
    return CaseResult(
        case=case,
        analysis=analysis,
        accepted={s.skill.code for s in observed if s.decision == MatchDecision.ACCEPT},
        observed={s.skill.code for s in observed},
        inferred={
            s.skill.code for s in analysis.skills if s.evidence_kind == EvidenceKind.INFERRED
        },
        role=analysis.role.role.code if analysis.role else None,
        role_decision=analysis.role.decision.value if analysis.role else None,
    )


def evaluate_gold(intel: JobIntelligence, gold: GoldFile, settings: dict[str, Any]) -> EvalReport:
    return EvalReport("Gold set", [run_case(intel, case) for case in gold.cases], settings)


def evaluate_synthetic(
    intel: JobIntelligence,
    dataset: dict[str, list[dict[str, Any]]],
    sample: int,
    settings: dict[str, Any],
) -> EvalReport:
    """Every k-th synthetic posting, scored against the generator's ground-truth links."""
    postings = dataset["job_posting"]
    step = max(1, len(postings) // max(1, sample))
    chosen = postings[::step][:sample]
    skill_code = {r["id"]: r["code"] for r in dataset["skill"]}
    role_code = {r["id"]: r["code"] for r in dataset["job_role"]}
    sector_code = {r["id"]: r["code"] for r in dataset["sector"]}
    truth: dict[Any, list[str]] = defaultdict(list)
    for link in dataset["posting_skill"]:
        truth[link["posting_id"]].append(skill_code[link["skill_id"]])
    roles = {link["posting_id"]: role_code[link["role_id"]] for link in dataset["posting_role"]}
    results = []
    for posting in chosen:
        case = GoldCase(
            id=str(posting["id"])[:8],
            categories=[f"synthetic-{posting['language']}"],
            language=posting["language"],
            sector=sector_code.get(posting["sector_id"]),
            title=posting["title"],
            description=posting["description"],
            expected_skills=sorted(truth[posting["id"]]),
            expected_role=roles.get(posting["id"]),
        )
        results.append(run_case(intel, case))
    return EvalReport("Synthetic postings vs generator ground truth", results, settings)


# --------------------------------------------------------------------------- report
def format_report(report: EvalReport, *, details: bool = True) -> str:
    s = report.summary()
    acc, obs = s["accepted"], s["accepted_or_review"]
    lines = [
        f"### {report.title}: {s['examples']} examples",
        "",
        "Settings: " + ", ".join(f"{k} = {v}" for k, v in report.settings.items()),
        "",
        "| Skills (OBSERVED) | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
        _metrics_row("accepted only", acc),
        _metrics_row("accepted + review", obs),
        "",
        f"**Role accuracy:** {s['role_accuracy']:.0%} "
        f"({sum(r.role_correct for r in report.results)}/{len(report.results)}). "
        f"INFERRED skills proposed: {s['inferred_skills']} (of which "
        f"{s['inferred_that_were_expected']} were stated in the gold labels; inferred skills "
        "are hints and are always reviewed).",
        "",
        "| Category | Examples | Precision | Recall | F1 | Role accuracy |",
        "|---|---|---|---|---|---|",
    ]
    categories: dict[str, list[CaseResult]] = defaultdict(list)
    for r in report.results:
        for category in r.case.categories:
            categories[category].append(r)
    for category, cases in sorted(categories.items()):
        c = report.counts("observed", cases)
        lines.append(
            f"| {category} | {len(cases)} | {c.precision:.2f} | {c.recall:.2f} | {c.f1:.2f} | "
            f"{report.role_accuracy(cases):.0%} |"
        )
    if not details:
        return "\n".join(lines) + "\n"

    missed, false, roles, low, unknown = [], [], [], [], []
    for r in report.results:
        excerpt = _excerpt(r.case)
        for code in sorted(r.expected - r.observed):
            missed.append(f"| {r.case.id} | {code} | {excerpt} |")
        by_code = {h.skill.code: h for h in r.analysis.observed}
        for code in sorted(r.observed - r.expected - set(r.case.optional_skills)):
            h = by_code[code]
            false.append(
                _row(r.case.id, code, h.method.value, f"{h.confidence:.2f}", _cell(h.matched_text))
            )
        if not r.role_correct:
            method = r.analysis.role.method.value if r.analysis.role else "-"
            confidence = f"{r.analysis.role.confidence:.2f}" if r.analysis.role else "-"
            roles.append(
                f"| {r.case.id} | {r.case.expected_role or '(none)'} | {r.role or '(none)'} | "
                f"{method} | {confidence} | {_cell(r.case.title)} |"
            )
        for h in r.analysis.observed:
            if h.decision == MatchDecision.REVIEW:
                ok = "yes" if h.skill.code in r.expected | set(r.case.optional_skills) else "no"
                low.append(
                    _row(
                        r.case.id,
                        h.skill.code,
                        h.method.value,
                        f"{h.confidence:.2f}",
                        ok,
                        _cell(h.matched_text),
                    )
                )
        for u in r.analysis.unknown:
            unknown.append(f"| {r.case.id} | {_cell(u.text)} |")
    lines += ["", f"#### Missed skills ({len(missed)})", ""]
    lines += (
        ["| Example | Expected skill | Text |", "|---|---|---|", *missed] if missed else ["None."]
    )
    lines += ["", f"#### False matches ({len(false)})", ""]
    lines += (
        [
            "| Example | Wrong skill | Method | Confidence | Matched words |",
            "|---|---|---|---|---|",
            *false,
        ]
        if false
        else ["None."]
    )
    lines += ["", f"#### Incorrect roles ({len(roles)})", ""]
    lines += (
        [
            "| Example | Expected | Predicted | Method | Confidence | Title |",
            "|---|---|---|---|---|---|",
            *roles,
        ]
        if roles
        else ["None."]
    )
    lines += ["", f"#### Low-confidence (review) skills ({len(low)})", ""]
    lines += (
        [
            "| Example | Skill | Method | Confidence | Correct? | Matched words |",
            "|---|---|---|---|---|---|",
            *low,
        ]
        if low
        else ["None."]
    )
    lines += [
        "",
        f"#### Phrases sent to the review queue as possible NEW skills ({len(unknown)})",
        "",
    ]
    lines += ["| Example | Phrase |", "|---|---|", *unknown] if unknown else ["None."]
    return "\n".join(lines) + "\n"


def _row(*cells: object) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _metrics_row(label: str, m: dict[str, Any]) -> str:
    return _row(
        label,
        f"{m['precision']:.2f}",
        f"{m['recall']:.2f}",
        f"{m['f1']:.2f}",
        m["tp"],
        m["fp"],
        m["fn"],
    )


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "/").replace("\n", " ")[:80]


def _excerpt(case: GoldCase) -> str:
    return _cell(f"{case.title}: {case.description or '(no description)'}")
