"""The whole pipeline with routing and weather faked: ETA -> forecast hour -> risk -> ranking."""

from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from planner.services import planner
from planner.services.checkpoints import TimedPath
from planner.services.geo import METERS_PER_MILE, cumulative
from planner.services.routing import RouteOption
from planner.services.weather import HourlySeries

DEPART = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
GUSTY_HOUR = 2  # only 14:00 has dangerous wind


def straight_route(lon: float, miles: float, hours: float) -> RouteOption:
    n = 41
    deg = miles * METERS_PER_MILE / 111_195
    seg_m = [miles * METERS_PER_MILE / (n - 1)] * (n - 1)
    seg_s = [hours * 3600 / (n - 1)] * (n - 1)
    points = [(30 + i * deg / (n - 1), lon) for i in range(n)]
    return RouteOption(TimedPath(points, cumulative(seg_m), cumulative(seg_s)), road_summary="")


def fake_forecast(points, start, end):
    hours = int((end - start).total_seconds() // 3600) + 1
    wind = [50.0 if h == GUSTY_HOUR else 5.0 for h in range(hours)]
    zero = [0.0] * hours
    return [HourlySeries(start, wind, wind, zero, zero) for _ in points]


@pytest.fixture
def plan():
    fast = straight_route(-96.0, miles=100, hours=2)  # 50 mph
    slow = straight_route(-95.0, miles=100, hours=4)  # 25 mph
    with (
        mock.patch.object(planner, "get_route_options", return_value=[fast, slow]),
        mock.patch.object(planner, "fetch_hourly", side_effect=fake_forecast) as forecast,
    ):
        result = planner.plan_trip(
            (30, -96), (31.4, -96), DEPART, load_lbs=35_000, interval_miles=25
        )
    return result, forecast


def test_checkpoint_weather_comes_from_the_hour_of_its_eta(plan):
    result, _ = plan
    a, b = result["routes"]
    # A reaches miles 0/25/50/75/100 at +0/30/60/90/120 min -> wind hours 0/1/1/2/2.
    assert [cp["wind_mph"] for cp in a["checkpoints"]] == [5, 5, 5, 50, 50]
    # B is twice as slow: +0/60/120/180/240 min -> only mile 50 is at 14:00.
    assert [cp["wind_mph"] for cp in b["checkpoints"]] == [5, 5, 50, 5, 5]
    assert a["checkpoints"][3]["eta"] == (DEPART + timedelta(minutes=90)).isoformat()


def test_load_rule_and_risk_miles_flow_into_the_recommendation(plan):
    result, _ = plan
    a, b = result["routes"]
    # 50 mph with 35,000 lb is No Travel. A: miles 75 (25 mi) + 100 (12.5 mi); B: mile 50 (25 mi).
    assert a["risk_miles"]["No Travel"] == 37.5
    assert b["risk_miles"]["No Travel"] == 25
    assert a["checkpoints"][3]["driver"] == "wind + load"
    assert result["recommended_route_id"] == "B"
    assert result["recommendation_reasons"] == ["25 Severe miles vs 37.5 on Route A"]
    assert a["why_not_recommended"] == "Route B is recommended: 25 Severe miles vs 37.5 on Route A"
    assert b["why_not_recommended"] is None
    assert any("No Travel" in w for w in result["warnings"])


def test_forecast_window_covers_every_eta(plan):
    _, forecast = plan
    _, start, end = forecast.call_args.args
    assert start == DEPART
    assert end >= DEPART + timedelta(hours=4)
