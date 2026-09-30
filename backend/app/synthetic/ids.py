"""Deterministic IDs for synthetic rows.

Every synthetic row's UUID is derived from its natural key (e.g. "institute:EX-ITI-A"), so
the same record gets the same ID on every run and every machine. Reloading the dataset
therefore updates rows in place, and links from other tables (a demo login that belongs to
Example ITI A, a validation vote by an Example employer) keep working.
"""

import uuid

# Fixed namespace for KaushalSetu synthetic data (never change it: all IDs would change).
NAMESPACE = uuid.UUID("7d6f3c1e-2b8a-5f4e-9c3d-4a1b0e6f8d20")


def synthetic_id(kind: str, *parts: object) -> uuid.UUID:
    """synthetic_id("institute", "EX-ITI-A") -> the same UUID every time."""
    return uuid.uuid5(NAMESPACE, f"{kind}:" + "|".join(str(part) for part in parts))
