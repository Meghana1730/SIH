"""Skill matching tests.

Most tests use a tiny FAKE embedder (word-overlap vectors) so they are fast and need no model
download; they check the pipeline order, thresholds, pgvector search and LLM-fallback rules.
The evaluation test at the end uses the REAL embedding model and is skipped if the model or
sentence-transformers is not installed.
"""

import dataclasses

import pytest
from sqlalchemy import update

from app.config import get_config
from app.models import Skill, SkillAlias
from app.nlp.embeddings import EmbeddingUnavailable, SentenceTransformerEmbedder
from app.nlp.evaluation import evaluate, format_report, load_eval_set, seed_vocabulary, summarize
from app.nlp.skill_embeddings import embed_vocabulary, nearest_skills
from app.nlp.skill_matcher import SkillMatcher
from app.nlp.text import normalize_text
from tests.helpers import FakeEmbedder

pytestmark = pytest.mark.db


@pytest.fixture
def config():
    return get_config()


@pytest.fixture
def vocab(db_session):
    """The evaluation vocabulary (17 synthetic skills + aliases) in the test database."""
    vocabulary, _ = load_eval_set()
    seed_vocabulary(db_session, vocabulary, source_ref="tests")
    return db_session


@pytest.fixture
def fake(vocab) -> FakeEmbedder:
    embedder = FakeEmbedder()
    embed_vocabulary(vocab, embedder)
    return embedder


def with_llm_fallback_enabled(config):
    llm = config.llm.llm
    task = llm.tasks.skill_match_fallback.model_copy(update={"enabled": True})
    tasks = llm.tasks.model_copy(update={"skill_match_fallback": task})
    llm = llm.model_copy(update={"provider": "mock", "mode": "live", "tasks": tasks})
    return dataclasses.replace(config, llm=config.llm.model_copy(update={"llm": llm}))


# ================================================================ normalisation
def test_normalize_text_ignores_case_spacing_and_punctuation():
    assert normalize_text("  EV-Diagnostics ") == "ev diagnostics"
    assert normalize_text("lockout/tagout") == "lockout tagout"
    assert normalize_text("Motor   Rewinding.") == "motor rewinding"


def test_normalize_text_keeps_devanagari_vowel_signs():
    # Vowel signs such as "ि" and "ा" are marks, not punctuation: they must survive.
    assert normalize_text("घर की वायरिंग") == "घर की वायरिंग"
    assert normalize_text(" सोलर-पैनल  लगाना ") == "सोलर पैनल लगाना"


# ================================================================ pipeline steps
def test_exact_name_match(vocab, config):
    result = SkillMatcher(vocab, config).match("  ev   DIAGNOSTICS ")
    assert (result.method, result.decision, result.confidence) == ("exact", "accept", 1.0)
    assert result.matched_skill.code == "ev-diagnostics"


def test_alias_match_in_hindi(vocab, config):
    result = SkillMatcher(vocab, config).match("सोलर पैनल लगाना")
    assert (result.method, result.decision) == ("alias", "accept")
    assert result.matched_skill.code == "rooftop-solar-installation"


def test_fuzzy_match_catches_spelling_mistakes(vocab, config):
    result = SkillMatcher(vocab, config).match("Domestic Wirring")
    assert (result.method, result.decision) == ("fuzzy", "accept")
    assert result.matched_skill.code == "domestic-wiring"
    assert config.scoring.skill_matching.fuzzy.min_score <= result.confidence < 1.0


def test_very_short_inputs_skip_fuzzy_matching(vocab, config):
    result = SkillMatcher(vocab, config).match("EVD")
    assert result.decision == "no_match"
    assert not any(c.method == "fuzzy" for c in result.alternatives)


def test_without_embeddings_meaning_is_not_guessed(vocab, config):
    result = SkillMatcher(vocab, config, embedder=None).match("EV troubleshooting")
    assert (result.decision, result.matched_skill) == ("no_match", None)
    assert result.note == "embeddings are switched off"


def test_embedding_match_uses_pgvector(fake, vocab, config):
    result = SkillMatcher(vocab, config, fake).match("EV troubleshooting")
    assert result.method == "embedding"
    assert result.matched_skill.code == "ev-diagnostics"
    as_json = result.to_dict()
    assert as_json["matched_skill"] == "EV Diagnostics"
    assert set(as_json) >= {"input", "matched_skill", "confidence", "method", "similarity"}


def test_fuzzy_near_misses_never_decide_a_match(fake, vocab, config):
    # "accounting" is spelled a bit like "grounding", but that is not evidence of meaning.
    result = SkillMatcher(vocab, config, fake).match("Accounting")
    assert result.method != "fuzzy"
    assert result.decision == "no_match"


def test_vectors_from_another_model_are_never_compared(fake, vocab, config):
    for model in (Skill, SkillAlias):
        vocab.execute(update(model).values(embedding_model="some-other-model"))
    assert nearest_skills(vocab, fake.embed_queries(["EV diagnostics"])[0], fake.space, 5) == []
    result = SkillMatcher(vocab, config, fake).match("EV troubleshooting")
    assert result.decision == "no_match"


def test_missing_model_falls_back_gracefully(vocab, config, tmp_path):
    embedder = SentenceTransformerEmbedder(config.llm.embeddings, tmp_path / "no-model-here")
    with pytest.raises(EmbeddingUnavailable, match="download_embedding_model"):
        embedder.embed_queries(["anything"])
    matcher = SkillMatcher(vocab, config, embedder)
    assert matcher.match("Domestic Wirring").method == "fuzzy"  # other steps still work
    fallback = matcher.match("EV troubleshooting")
    assert fallback.decision == "no_match"
    assert fallback.note.startswith("embeddings unavailable")


def test_decisions_follow_the_configured_thresholds(vocab, config):
    stricter = config.scoring.skill_matching.model_copy(update={"auto_accept_confidence": 0.99})
    scoring = config.scoring.model_copy(update={"skill_matching": stricter})
    strict_config = dataclasses.replace(config, scoring=scoring)
    result = SkillMatcher(vocab, strict_config).match("Domestic Wirring")  # fuzzy ~0.97
    assert (result.method, result.decision) == ("fuzzy", "review")


def test_similarity_is_rescaled_with_the_configured_floor(vocab, config):
    matcher = SkillMatcher(vocab, config)
    floor = config.llm.embeddings.similarity_floor
    assert matcher._calibrate(floor) == 0.0
    assert matcher._calibrate(floor - 0.1) == 0.0
    assert matcher._calibrate(1.0) == 1.0
    assert matcher._calibrate(floor + (1 - floor) / 2) == pytest.approx(0.5)


def test_match_many_gives_the_same_results_with_one_embedding_batch(fake, vocab, config):
    phrases = ["EV Diagnostics", "HV safety", "Domestic Wirring", "EV troubleshooting", "Cooking"]
    one_by_one = [SkillMatcher(vocab, config, fake).match(p).to_dict() for p in phrases]

    batches = []
    original = fake.embed_queries

    def counting(texts):
        batches.append(list(texts))
        return original(texts)

    fake.embed_queries = counting
    together = [r.to_dict() for r in SkillMatcher(vocab, config, fake).match_many(phrases)]
    assert together == one_by_one
    # Exact and alias matches need no embedding; the rest are embedded in a single call.
    assert batches == [["Domestic Wirring", "EV troubleshooting", "Cooking"]]


# ================================================================ LLM fallback
def test_llm_fallback_only_when_unsure_and_only_among_candidates(fake, vocab, config):
    calls = []

    def fallback(text, candidates):
        calls.append(text)
        return candidates[-1].skill.code

    matcher = SkillMatcher(vocab, with_llm_fallback_enabled(config), fake, llm_fallback=fallback)

    assert matcher.match("EV Diagnostics").method == "exact"
    assert calls == []  # certain matches never reach the LLM

    unsure = matcher.match("diagnostics of old cars")
    assert calls == ["diagnostics of old cars"]
    assert unsure.method == "llm"
    assert unsure.decision == "review"  # an LLM answer is always checked by a human
    assert unsure.confidence == config.scoring.skill_matching.llm_fallback_max_confidence


def test_llm_fallback_cannot_invent_a_skill(fake, vocab, config):
    matcher = SkillMatcher(
        vocab, with_llm_fallback_enabled(config), fake, llm_fallback=lambda *_: "made-up-skill"
    )
    result = matcher.match("diagnostics of old cars")
    assert result.method != "llm"


def test_llm_fallback_is_off_unless_configured(fake, vocab, config):
    calls = []
    llm = config.llm.llm.model_copy(update={"mode": "off"})
    off = dataclasses.replace(config, llm=config.llm.model_copy(update={"llm": llm}))
    matcher = SkillMatcher(vocab, off, fake, llm_fallback=lambda t, c: calls.append(t))
    matcher.match("diagnostics of old cars")
    assert calls == []  # LLM mode "off": the fallback is never called


# ================================================================ real model evaluation
@pytest.mark.embeddings
def test_matcher_quality_on_the_evaluation_set(db_session, config):
    """Minimum quality bars on data/gold/skill_matching_cases.yaml with the REAL model.
    Measured on 2026-09-29 (e5-small, floor 0.70): exact 5/5, alias 6/6, spelling 8/8,
    semantic 14/15 found, 0 wrong skills, 0 false accepts, 1 false review."""
    embedder = SentenceTransformerEmbedder(config.llm.embeddings, config.embedding_model_dir)
    try:
        embedder.embed_queries(["warm-up"])
    except EmbeddingUnavailable as reason:
        pytest.skip(str(reason))

    vocabulary, cases = load_eval_set()
    seed_vocabulary(db_session, vocabulary, source_ref="tests")
    embed_vocabulary(db_session, embedder)
    outcomes = evaluate(SkillMatcher(db_session, config, embedder), cases)
    print("\n" + format_report(outcomes, "Skill matching evaluation"))

    summary = summarize(outcomes)
    per = summary["per_category"]
    assert per["exact"]["correct accept"] == 5
    assert per["alias"]["correct accept"] == 6
    assert per["spelling"]["correct accept"] >= 7
    # Semantic matching is useful but not perfect: require most, not all.
    assert per["semantic"]["correct accept"] + per["semantic"]["correct review"] >= 12
    assert summary["wrong"] == 0
    assert summary["unrelated_false_accepts"] == 0
    assert summary["unrelated_false_reviews"] <= 2
