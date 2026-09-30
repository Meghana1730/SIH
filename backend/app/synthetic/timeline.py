"""Calendar helpers: quarters ("2026Q3") and academic years ("2025-26")."""

from datetime import date, timedelta

from app.config.base import quarter_index


def quarter_from_index(index: int) -> str:
    return f"{index // 4}Q{index % 4 + 1}"


def quarter_range(start: str, end: str) -> list[str]:
    """['2025Q2', '2025Q3', ...] from start to end, both included."""
    return [quarter_from_index(i) for i in range(quarter_index(start), quarter_index(end) + 1)]


def shift_quarter(quarter: str, quarters: int) -> str:
    return quarter_from_index(quarter_index(quarter) + quarters)


def quarter_of(day: date) -> str:
    return f"{day.year}Q{(day.month - 1) // 3 + 1}"


def quarter_start(quarter: str) -> date:
    year, part = quarter.split("Q")
    return date(int(year), 3 * (int(part) - 1) + 1, 1)


def quarter_end(quarter: str) -> date:
    return quarter_start(shift_quarter(quarter, 1)) - timedelta(days=1)


def academic_year_start(year: str) -> int:
    """'2025-26' -> 2025."""
    return int(year[:4])
