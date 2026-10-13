"""Hourly Open-Meteo forecasts in mph and in/hr.

Precipitation values are totals for the hour ending at their timestamp; wind is
instantaneous. Rain is `rain` + `showers`. Gusts are display-only.
"""

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from django.conf import settings
from django.core.cache import cache

from .geo import LatLon
from .upstream import UpstreamError, get_json

HOURLY_VARS = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
EXPECTED_UNITS = {
    "wind_speed_10m": {"mp/h", "mph"},
    "wind_gusts_10m": {"mp/h", "mph"},
    "rain": {"inch"},
    "showers": {"inch"},
    "snowfall": {"inch"},
}
SNAP_DEG = 0.1  # ~11 km; nearby points share a forecast
BATCH_SIZE = 50
CACHE_SECONDS = 30 * 60
SECONDS_PER_HOUR = 3600
FORECAST_HORIZON = timedelta(days=15)


@dataclass(frozen=True)
class Conditions:
    """Weather the truck meets at one checkpoint."""

    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


def _round_half_up(value: float) -> int:
    """Round to the nearest integer, halves up."""
    return math.floor(value + 0.5)  # round() rounds halves to even


@dataclass(frozen=True)
class HourlySeries:
    """One location's hourly forecast, starting at `start`."""

    start: datetime  # UTC
    wind: list[float]
    gust: list[float]
    rain: list[float]
    snow: list[float]

    def at(self, when: datetime) -> Conditions:
        """Wind from the nearest hour; rain and snow from the hour containing `when`."""
        hours_since_start = (when - self.start).total_seconds() / SECONDS_PER_HOUR
        last_hour = len(self.wind) - 1
        nearest_hour = min(max(_round_half_up(hours_since_start), 0), last_hour)
        containing_hour = min(max(math.ceil(hours_since_start), 0), last_hour)
        return Conditions(
            wind_mph=self.wind[nearest_hour],
            gust_mph=self.gust[nearest_hour],
            rain_in_hr=self.rain[containing_hour],
            snow_in_hr=self.snow[containing_hour],
        )


def floor_hour(dt: datetime) -> datetime:
    """`dt` in UTC, truncated to the hour."""
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def snap(point: LatLon) -> LatLon:
    """Snap a point to the SNAP_DEG grid."""
    return round(round(point[0] / SNAP_DEG) * SNAP_DEG, 4), round(
        round(point[1] / SNAP_DEG) * SNAP_DEG, 4
    )


def _cache_key(point: LatLon, start: datetime, hours: int) -> str:
    """Cache key for one location and time window."""
    return f"wx:{point[0]:.4f}:{point[1]:.4f}:{start:%Y%m%d%H}:{hours}"


def _numbers(values) -> list[float]:
    """Floats, assuming a missing value means none reported (0 wind or precipitation)."""
    return [float(value) if value is not None else 0.0 for value in values]


def check_units(units: dict) -> None:
    """Raise if Open-Meteo didn't answer in mph and inches."""
    wrong = {var: units.get(var) for var, ok in EXPECTED_UNITS.items() if units.get(var) not in ok}
    if wrong:
        raise UpstreamError(f"Weather service returned unexpected units: {wrong}")


def _fetch_batch(points: list[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
    """One Open-Meteo request for up to BATCH_SIZE points."""
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
    }
    if settings.OPEN_METEO_API_KEY:
        params["apikey"] = settings.OPEN_METEO_API_KEY
    data = get_json(
        f"{settings.OPEN_METEO_BASE_URL}/v1/forecast", params, service="Weather service"
    )
    locations = data if isinstance(data, list) else [data]  # a single location isn't wrapped
    if len(locations) != len(points):
        raise UpstreamError("Weather service returned an unexpected number of locations")
    forecasts = []
    for location in locations:
        check_units(location.get("hourly_units", {}))
        hourly = location["hourly"]
        large_scale_rain = _numbers(hourly["rain"])
        showers = _numbers(hourly["showers"])
        forecasts.append(
            HourlySeries(
                start=start,
                wind=_numbers(hourly["wind_speed_10m"]),
                gust=_numbers(hourly["wind_gusts_10m"]),
                rain=[
                    rain + shower for rain, shower in zip(large_scale_rain, showers, strict=True)
                ],
                snow=_numbers(hourly["snowfall"]),
            )
        )
    return forecasts


def fetch_hourly(points: list[LatLon], start: datetime, end: datetime) -> list[HourlySeries]:
    """Hourly series covering [start, end] (UTC, floored to the hour) for each point, in order."""
    start, end = floor_hour(start), floor_hour(end)
    if end - start > FORECAST_HORIZON or end > floor_hour(datetime.now(UTC)) + FORECAST_HORIZON:
        raise UpstreamError(
            "Trip extends beyond the available forecast window (~15 days)",
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    hour_count = int((end - start).total_seconds() // SECONDS_PER_HOUR) + 1

    snapped_points = [snap(point) for point in points]
    unique_points = list(dict.fromkeys(snapped_points))
    cache_keys = {point: _cache_key(point, start, hour_count) for point in unique_points}
    cached = cache.get_many(cache_keys.values())
    forecast_by_point: dict[LatLon, HourlySeries] = {
        point: cached[key] for point, key in cache_keys.items() if key in cached
    }

    uncached = [point for point in unique_points if point not in forecast_by_point]
    batches = [uncached[i : i + BATCH_SIZE] for i in range(0, len(uncached), BATCH_SIZE)]
    if batches:
        newly_fetched: dict[str, HourlySeries] = {}
        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as pool:
            batch_results = pool.map(lambda batch: _fetch_batch(batch, start, end), batches)
            for batch, forecasts in zip(batches, batch_results, strict=True):
                for point, forecast in zip(batch, forecasts, strict=True):
                    forecast_by_point[point] = forecast
                    newly_fetched[cache_keys[point]] = forecast
        cache.set_many(newly_fetched, CACHE_SECONDS)

    return [forecast_by_point[point] for point in snapped_points]
