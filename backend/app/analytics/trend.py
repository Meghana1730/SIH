"""The skill-trend rule (docs/03-prd.md §7.5, config/scoring.yaml `trend`), in one place.

EMERGING  mentions in the second half of the window grew by >= min_relative_growth over the
          first half, and the second half has >= min_mentions
DECLINING the last `consecutive_quarter_drops` quarter-on-quarter changes are all falls, and
          the fall over that run is >= min_relative_decline
STABLE    otherwise
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.scoring import TrendConfig
from app.models.enums import TrendStatus


@dataclass(frozen=True)
class Trend:
    status: TrendStatus
    window: list[int]
    growth: float | None  # second half vs first half of the window
    recent_mentions: int
    drops: int  # consecutive quarter-on-quarter falls at the end of the window
    decline: float | None  # fall over those consecutive drops

    def describe(self) -> str:
        growth = "n/a" if self.growth is None else f"{self.growth:+.0%}"
        decline = "n/a" if self.decline is None else f"{self.decline:.0%}"
        return (
            f"{self.status.value}: window {self.window}, growth {growth}, recent mentions "
            f"{self.recent_mentions}, consecutive drops {self.drops}, decline {decline}"
        )


def classify_trend(series: list[int], rules: TrendConfig) -> Trend:
    window = list(series[-rules.window_quarters :])
    half = len(window) // 2
    earlier, recent = sum(window[:half]), sum(window[-half:]) if half else 0
    growth = None if earlier == 0 else (recent - earlier) / earlier
    drops = 0
    for i in range(len(window) - 1, 0, -1):
        if window[i] < window[i - 1]:
            drops += 1
        else:
            break
    run_start = window[len(window) - 1 - drops] if window else 0
    decline = None if drops == 0 or run_start == 0 else (run_start - window[-1]) / run_start
    grew = (growth is None and recent > 0) or (
        growth is not None and growth >= rules.emerging.min_relative_growth
    )
    emerging = recent >= rules.emerging.min_mentions and grew
    declining = (
        drops >= rules.declining.consecutive_quarter_drops
        and decline is not None
        and decline >= rules.declining.min_relative_decline
    )
    status = (
        TrendStatus.EMERGING
        if emerging
        else TrendStatus.DECLINING if declining else TrendStatus.STABLE
    )
    return Trend(status, window, growth, recent, drops, decline)
