"""Risk table and load rules.

Band lower bounds are inclusive (35.0 mph is High), except No Travel for rain and
snow, which the spec defines as strictly above 1.00 / 3.0 in/hr.
"""

from dataclasses import dataclass
from enum import IntEnum


class Risk(IntEnum):
    """Risk levels, ordered so max() gives the worst."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        """Display name, such as 'No Travel'."""
        return RISK_LABELS[self]


RISK_LABELS = {
    Risk.LOW: "Low",
    Risk.MODERATE: "Moderate",
    Risk.HIGH: "High",
    Risk.SEVERE: "Severe",
    Risk.NO_TRAVEL: "No Travel",
}

# Lower bounds of Moderate, High, Severe, No Travel.
WIND_BANDS_MPH = (25.0, 35.0, 45.0, 55.0)
# Lower bounds of Moderate, High, Severe; No Travel is above the last.
RAIN_BANDS_IN_HR = (0.10, 0.25, 0.50, 1.00)
SNOW_BANDS_IN_HR = (0.5, 1.0, 2.0, 3.0)

MODERATE_WIND_MPH, HIGH_WIND_MPH, SEVERE_WIND_MPH, NO_TRAVEL_WIND_MPH = WIND_BANDS_MPH
MAX_LOAD_IN_SEVERE_WIND_LBS = 30_000
MAX_LOAD_IN_HIGH_WIND_LBS = 40_000


def classify_wind(mph: float) -> Risk:
    """Risk level from the wind table alone, before load rules."""
    if mph >= NO_TRAVEL_WIND_MPH:
        return Risk.NO_TRAVEL
    if mph >= SEVERE_WIND_MPH:
        return Risk.SEVERE
    if mph >= HIGH_WIND_MPH:
        return Risk.HIGH
    if mph >= MODERATE_WIND_MPH:
        return Risk.MODERATE
    return Risk.LOW


def _classify_precip(rate: float, bands: tuple[float, float, float, float]) -> Risk:
    """Risk level from a rain or snow table, whose No Travel bound is exclusive."""
    moderate, high, severe, no_travel_above = bands
    if rate > no_travel_above:
        return Risk.NO_TRAVEL
    if rate >= severe:
        return Risk.SEVERE
    if rate >= high:
        return Risk.HIGH
    if rate >= moderate:
        return Risk.MODERATE
    return Risk.LOW


def classify_rain(in_per_hr: float) -> Risk:
    """Risk level for a rain rate in in/hr."""
    return _classify_precip(in_per_hr, RAIN_BANDS_IN_HR)


def classify_snow(in_per_hr: float) -> Risk:
    """Risk level for a snow rate in in/hr."""
    return _classify_precip(in_per_hr, SNOW_BANDS_IN_HR)


def apply_load_rules(wind_mph: float, load_lbs: float) -> tuple[Risk, str | None]:
    """Wind level after the load rules, and which rule applied (if any)."""
    base = classify_wind(wind_mph)
    if wind_mph >= NO_TRAVEL_WIND_MPH:
        return Risk.NO_TRAVEL, None
    if wind_mph >= SEVERE_WIND_MPH and load_lbs > MAX_LOAD_IN_SEVERE_WIND_LBS:
        return Risk.NO_TRAVEL, "45–54 mph wind with load over 30,000 lb"
    if wind_mph >= HIGH_WIND_MPH and load_lbs > MAX_LOAD_IN_HIGH_WIND_LBS:
        return Risk.SEVERE, "35–44 mph wind with load over 40,000 lb"
    return base, None


@dataclass(frozen=True)
class Assessment:
    """A checkpoint's overall risk and the level of each condition."""

    level: Risk
    wind_level: Risk
    rain_level: Risk
    snow_level: Risk
    load_note: str | None

    @property
    def drivers(self) -> list[str]:
        """Conditions at the overall level; empty when Low."""
        if self.level == Risk.LOW:
            return []
        named = (("wind", self.wind_level), ("rain", self.rain_level), ("snow", self.snow_level))
        return [name for name, lvl in named if lvl == self.level]

    @property
    def driver(self) -> str:
        """ "wind + load", "rain", "wind, snow", or "" when Low."""
        parts = list(self.drivers)
        if self.load_note and "wind" in parts:
            parts[parts.index("wind")] = "wind + load"
        return ", ".join(parts)


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> Assessment:
    """Overall risk: the worst of load-adjusted wind, rain and snow."""
    wind_level, load_note = apply_load_rules(wind_mph, load_lbs)
    rain_level = classify_rain(rain_in_hr)
    snow_level = classify_snow(snow_in_hr)
    return Assessment(
        level=max(wind_level, rain_level, snow_level),
        wind_level=wind_level,
        rain_level=rain_level,
        snow_level=snow_level,
        load_note=load_note,
    )
