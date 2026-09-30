"""Shared building blocks for the configuration models.

Design rules:
* Business values have NO defaults in Python. Every value must be written in config/*.yaml,
  so there is exactly one place where each number lives.
* Unknown keys are rejected (a typo such as `postngs:` fails loudly instead of being ignored).
* Loaded configuration is read-only (frozen).
"""

from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# A number between 0 and 1 (a share or a probability).
Fraction = Annotated[float, Field(ge=0, le=1)]
# A calendar quarter such as "2026Q3".
Quarter = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}Q[1-4]$")]
# Our internal codes (fit the database columns: sector.code and district.code are 40 chars).
SectorCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")]
DistrictCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}-[A-Z0-9-]{2,37}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

WEIGHT_TOLERANCE = 1e-6


def require_sum_to_one(weights: dict[str, float], label: str) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        parts = ", ".join(f"{name}={value:g}" for name, value in weights.items())
        raise ValueError(f"{label} must add up to 1.0 but add up to {total:g} ({parts})")


def duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def quarter_index(quarter: str) -> int:
    """'2026Q3' -> a running number, so quarters can be compared and counted."""
    year, part = quarter.split("Q")
    return int(year) * 4 + int(part) - 1


def quarters_inclusive(start: str, end: str) -> int:
    """Number of quarters from start to end, both included ('2025Q2'..'2026Q3' -> 6)."""
    return quarter_index(end) - quarter_index(start) + 1
