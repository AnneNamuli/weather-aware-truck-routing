"""Rank routes: no No Travel miles, then fewest Severe miles (No Travel counted as
Severe), fewest High miles, lowest average risk, shortest time.

Values are rounded before comparing so float noise can't decide a tie.
"""

from dataclasses import dataclass, field

from .geo import METERS_PER_MILE
from .risk import Risk


@dataclass
class RiskSummary:
    """A route's miles per risk level, average risk, duration and ranking key."""

    route_id: str
    miles: dict[Risk, float]
    avg_risk: float
    duration_s: float
    rank_key: tuple = field(init=False)

    @property
    def has_no_travel(self) -> bool:
        """Whether any No Travel miles remain after rounding."""
        return round(self.miles[Risk.NO_TRAVEL], 1) > 0

    @property
    def severe_miles(self) -> float:
        """Severe miles, counting No Travel miles as Severe."""
        return round(self.miles[Risk.SEVERE] + self.miles[Risk.NO_TRAVEL], 1)

    def __post_init__(self):
        self.rank_key = (
            self.has_no_travel,
            self.severe_miles,
            round(self.miles[Risk.HIGH], 1),
            round(self.avg_risk, 2),
            round(self.duration_s),
        )


def summarize(
    route_id: str, risk_per_covered_length: list[tuple[Risk, float]], duration_s: float
) -> RiskSummary:
    """`risk_per_covered_length`: (level, meters covered) per checkpoint."""
    miles_by_level = dict.fromkeys(Risk, 0.0)
    for level, covered_m in risk_per_covered_length:
        miles_by_level[level] += covered_m / METERS_PER_MILE
    total_miles = sum(miles_by_level.values())
    weighted_levels = sum(level * miles for level, miles in miles_by_level.items())
    avg_risk = weighted_levels / total_miles if total_miles else 0.0
    return RiskSummary(route_id, miles_by_level, avg_risk, duration_s)


def _format_duration(seconds: float) -> str:
    """Seconds as '4h 05m'."""
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _reason(best: RiskSummary, other: RiskSummary) -> str:
    """The first ranking criterion on which `best` beats `other`, as a phrase."""
    other_id = other.route_id
    no_travel, severe, high, avg_risk, travel_time = range(5)
    for criterion, (best_value, other_value) in enumerate(
        zip(best.rank_key, other.rank_key, strict=True)
    ):
        if best_value == other_value:
            continue
        if criterion == no_travel:
            no_travel_miles = other.miles[Risk.NO_TRAVEL]
            return f"avoids the {no_travel_miles:.1f} No Travel miles on Route {other_id}"
        if criterion in (severe, high):
            label = "Severe" if criterion == severe else "High"
            return f"{best_value:g} {label} miles vs {other_value:g} on Route {other_id}"
        if criterion == avg_risk:
            return (
                f"lower average risk than Route {other_id} ({best_value:.2f} vs {other_value:.2f})"
            )
        assert criterion == travel_time
        best_time, other_time = _format_duration(best_value), _format_duration(other_value)
        return f"faster than Route {other_id} ({best_time} vs {other_time})"
    return f"identical risk and time to Route {other_id}"


def recommend(summaries: list[RiskSummary]) -> tuple[list[RiskSummary], list[str]]:
    """Summaries best first, and why the best beat each of the others."""
    ranked = sorted(summaries, key=lambda summary: summary.rank_key)
    best = ranked[0]
    return ranked, [_reason(best, other) for other in ranked[1:]]
