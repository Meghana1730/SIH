"""Which database tables the synthetic dataset fills, in load order (parents first).

`dataset` is the key in config/synthetic.yaml `source_ids`, so each table's rows carry the
right source ID (e.g. job_posting -> Y01). Three link tables have no `source` column; they
name their parent instead, and their rows count as synthetic through `is_synthetic` and
the parent.
"""

from dataclasses import dataclass

from sqlalchemy import Table

from app.models import Base


@dataclass(frozen=True)
class SyntheticTable:
    name: str
    dataset: str  # key in config.synthetic.source_ids
    # For tables without a `source` column: (foreign-key column, parent table).
    parent: tuple[str, str] | None = None

    @property
    def table(self) -> Table:
        return Base.metadata.tables[self.name]

    @property
    def has_source(self) -> bool:
        return "source" in self.table.c

    @property
    def is_link(self) -> bool:
        """Composite primary key and nothing points at it: safe to delete and re-insert."""
        return len(self.table.primary_key.columns) > 1


# Reference rows the synthetic data points at. They come from config (scope.yaml,
# sectors.yaml), are NOT synthetic, and are created by the loader only if missing.
REFERENCE_TABLES = ("sector", "district")

SYNTHETIC_TABLES: tuple[SyntheticTable, ...] = (
    SyntheticTable("skill", "demo_vocabulary"),
    SyntheticTable("skill_alias", "demo_vocabulary"),
    SyntheticTable("job_role", "demo_vocabulary"),
    SyntheticTable("role_skill", "demo_vocabulary"),
    SyntheticTable("role_edge", "demo_vocabulary"),
    SyntheticTable("course", "demo_vocabulary"),
    SyntheticTable("course_module", "demo_vocabulary"),
    SyntheticTable("module_skill", "demo_vocabulary"),
    SyntheticTable("course_role", "demo_vocabulary"),
    SyntheticTable("equipment", "equipment_costs"),
    SyntheticTable("skill_equipment", "demo_vocabulary"),
    SyntheticTable("institute", "institutes"),
    SyntheticTable("course_offering", "course_offerings"),
    SyntheticTable("trainer", "trainers"),
    SyntheticTable("trainer_skill", "trainers"),
    SyntheticTable("institute_equipment", "institute_equipment"),
    SyntheticTable("employer", "employers"),
    SyntheticTable("sector_event", "sector_events"),
    SyntheticTable("consultation", "consultations"),
    SyntheticTable("consultation_insight", "consultations", ("consultation_id", "consultation")),
    SyntheticTable("employer_survey_response", "employer_survey_responses"),
    SyntheticTable("job_posting", "job_postings"),
    SyntheticTable("posting_role", "job_postings", ("posting_id", "job_posting")),
    SyntheticTable("posting_skill", "job_postings", ("posting_id", "job_posting")),
    SyntheticTable("candidate", "candidates"),
    SyntheticTable("candidate_skill", "candidates"),
    SyntheticTable("enrollment", "enrollments"),
    SyntheticTable("placement_outcome", "placement_outcomes"),
    SyntheticTable("employer_rating", "employer_ratings"),
)
BY_NAME = {t.name: t for t in SYNTHETIC_TABLES}

# Filled by the database, the loader or other tools; never part of the export.
_NOT_EXPORTED = {"created_at", "updated_at", "ingestion_run_id", "embedding", "embedding_model"}


def columns(table_name: str) -> list[str]:
    """Columns the generator writes for a table: primary key first, then table order."""
    table = Base.metadata.tables[table_name]
    keys = [c.name for c in table.primary_key.columns]
    rest = [c.name for c in table.columns if c.name not in _NOT_EXPORTED and c.name not in keys]
    return keys + rest
