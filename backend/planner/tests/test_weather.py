from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from django.core.cache import cache

from planner.services import weather
from planner.services.weather import HourlySeries, fetch_hourly, snap

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_cache(db):
    cache.clear()


def series(n=5) -> HourlySeries:
    # Value at hour h is h (wind) or h/10 (rain) so indices are easy to read.
    return HourlySeries(
        start=START,
        wind=[float(h) for h in range(n)],
        gust=[float(h) for h in range(n)],
        rain=[h / 10 for h in range(n)],
        snow=[h / 100 for h in range(n)],
    )


@pytest.mark.parametrize(
    "minutes, wind_idx, precip_idx",
    [
        (0, 0, 0),
        (20, 0, 1),  # 12:20 -> nearest wind 12:00; precip total for 12:00–13:00 (stamped 13:00)
        (30, 1, 1),  # halves round up
        (40, 1, 1),
        (60, 1, 1),
        (150, 3, 3),  # 2.5 h: round() would give 2
        (61, 1, 2),
        (10_000, 4, 4),  # clamped to the end of the series
    ],
)
def test_conditions_at_eta(minutes, wind_idx, precip_idx):
    c = series().at(START + timedelta(minutes=minutes))
    assert c.wind_mph == wind_idx
    assert c.rain_in_hr == pytest.approx(precip_idx / 10)
    assert c.snow_in_hr == pytest.approx(precip_idx / 100)


def test_snap_groups_nearby_points():
    assert snap((32.7767, -96.797)) == snap((32.80, -96.82)) == (32.8, -96.8)


def test_fetch_dedupes_and_caches_points():
    calls = []

    def fake_batch(points, start, end):
        calls.append(list(points))
        return [series() for _ in points]

    now = datetime.now(UTC)
    with mock.patch.object(weather, "_fetch_batch", side_effect=fake_batch):
        pts = [(32.7767, -96.797), (32.80, -96.82), (30.0, -95.0)]
        out = fetch_hourly(pts, now, now + timedelta(hours=3))
        assert len(out) == 3 and out[0] is out[1]
        assert calls == [[(32.8, -96.8), (30.0, -95.0)]]

        fetch_hourly(pts, now, now + timedelta(hours=3))
        assert len(calls) == 1  # second call fully served from cache


def test_fetch_rejects_trip_beyond_forecast_horizon():
    now = datetime.now(UTC)
    with pytest.raises(weather.UpstreamError):
        fetch_hourly([(30, -95)], now, now + timedelta(days=20))


def test_units_are_checked():
    good = {
        "wind_speed_10m": "mp/h",
        "wind_gusts_10m": "mp/h",
        "rain": "inch",
        "showers": "inch",
        "snowfall": "inch",
    }
    weather.check_units(good)
    with pytest.raises(weather.UpstreamError, match="snowfall"):
        weather.check_units({**good, "snowfall": "cm"})
