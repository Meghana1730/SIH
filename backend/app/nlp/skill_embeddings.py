"""Compute and store embeddings for the skill vocabulary (skill names and aliases), and search
them with pgvector.

Vectors are tagged with the embedder's `space` (model + text prefix). Searches only compare
vectors from the same space, so switching models never mixes incompatible numbers; run
`python -m app.cli.embed_skills` again after changing the model or prefix.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Skill, SkillAlias
from app.nlp.embeddings import Embedder


@dataclass(frozen=True)
class EmbedReport:
    skills: int
    aliases: int


def embed_vocabulary(db: Session, embedder: Embedder, *, refresh: bool = False) -> EmbedReport:
    """Embed every skill name and alias that has no vector in the current space yet
    (or all of them with refresh=True). Does not commit."""

    def outdated(model):
        if refresh:
            return select(model)
        return select(model).where(
            or_(model.embedding.is_(None), model.embedding_model != embedder.space)
        )

    skills = list(db.scalars(outdated(Skill)))
    for skill, vector in zip(
        skills, embedder.embed_documents([s.name for s in skills]), strict=True
    ):
        skill.embedding, skill.embedding_model = vector, embedder.space

    aliases = list(db.scalars(outdated(SkillAlias)))
    for alias, vector in zip(
        aliases, embedder.embed_documents([a.alias for a in aliases]), strict=True
    ):
        alias.embedding, alias.embedding_model = vector, embedder.space

    db.flush()
    return EmbedReport(skills=len(skills), aliases=len(aliases))


@dataclass(frozen=True)
class VectorHit:
    skill_id: uuid.UUID
    code: str
    name: str
    matched_text: str  # the skill name or alias that was closest
    similarity: float  # cosine similarity, -1..1 (1 = same direction)


def nearest_skills(
    db: Session, query_vector: list[float], space: str, top_k: int
) -> list[VectorHit]:
    """The top_k most similar skills (best of name and aliases per skill), via pgvector."""
    hits: dict[uuid.UUID, VectorHit] = {}

    distance = Skill.embedding.cosine_distance(query_vector)
    by_name = (
        select(Skill.id, Skill.code, Skill.name, Skill.name, distance)
        .where(Skill.embedding_model == space)
        .order_by(distance)
        .limit(top_k)
    )
    alias_distance = SkillAlias.embedding.cosine_distance(query_vector)
    by_alias = (
        select(Skill.id, Skill.code, Skill.name, SkillAlias.alias, alias_distance)
        .join(Skill, Skill.id == SkillAlias.skill_id)
        .where(SkillAlias.embedding_model == space)
        .order_by(alias_distance)
        .limit(top_k)
    )
    for query in (by_name, by_alias):
        for skill_id, code, name, text, dist in db.execute(query):
            hit = VectorHit(skill_id, code, name, text, 1.0 - float(dist))
            if skill_id not in hits or hit.similarity > hits[skill_id].similarity:
                hits[skill_id] = hit
    return sorted(hits.values(), key=lambda h: h.similarity, reverse=True)[:top_k]
