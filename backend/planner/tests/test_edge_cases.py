"""Edge cases: tiny trips, missing data, too many or too few routes, bad input."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest import mock

import pytest
from django.test import Client

from planner.services import planner, routing, weather
from planner.services.checkpoints import (
    TimedPath,
    checkpoint_distances,
    coverage,
    sample_checkpoints,
)
from planner.services.geo import METERS_PER_MILE, cumulative
from planner.services.recommend import summarize
from planner.services.risk import Risk
from planner.services.routing import RouteOption
from planner.services.weather import HourlySeries

MILE = METERS_PER_MILE
DEPART = datetime(2026, 1, 1, 12, tzinfo=UTC)


def straight_route(miles: float, hours: float, lon: float = -96.0) -> RouteOption:
    vertex_count = 11
    lat_span = miles * MILE / 111_195
    points = [(30 + lat_span * i / (vertex_count - 1), lon) for i in range(vertex_count)]
    segment_m = [miles * MILE / (vertex_count - 1)] * (vertex_count - 1)
    segment_s = [hours * 3600 / (vertex_count - 1)] * (vertex_count - 1)
    return RouteOption(TimedPath(points, cumulative(segment_m), cumulative(segment_s)), "")


def calm_forecast(points, start, end):
    hours = int((end - start).total_seconds() // 3600) + 1
    zeros = [0.0] * hours
    return [HourlySeries(start, zeros, zeros, zeros, zeros) for _ in points]


def test_trip_shorter_than_one_interval_has_start_and_end_checkpoints():
    checkpoints = sample_checkpoints(straight_route(miles=3, hours=0.1).path, 10, DEPART)
    assert [round(cp.distance_m / MILE, 1) for cp in checkpoints] == [0, 3]
    assert sum(cp.covered_route_m for cp in checkpoints) == pytest.approx(3 * MILE)


def test_zero_length_route_gives_one_checkpoint_and_zero_average_risk():
    assert checkpoint_distances(0, 25 * MILE) == [0]
    assert coverage([0]) == [0.0]
    assert summarize("A", [(Risk.LOW, 0.0)], 0).avg_risk == 0.0


def test_forecast_lookup_before_the_series_uses_the_first_hour():
    series = HourlySeries(DEPART, [7.0, 9.0], [7.0, 9.0], [0.0, 0.2], [0.0, 0.0])
    assert series.at(DEPART - timedelta(hours=3)).wind_mph == 7.0


def test_missing_forecast_values_count_as_none_reported():
    response = {
        "hourly_units": dict.fromkeys(("wind_speed_10m", "wind_gusts_10m"), "mp/h")
        | dict.fromkeys(("rain", "showers", "snowfall"), "inch"),
        "hourly": {
            "wind_speed_10m": [None],
            "wind_gusts_10m": [None],
            "rain": [None],
            "showers": [0.1],
            "snowfall": [None],
        },
    }
    with mock.patch.object(weather, "get_json", return_value=response):
        [series] = weather._fetch_batch([(30.0, -96.0)], DEPART, DEPART)
    assert (series.wind[0], series.rain[0], series.snow[0]) == (0.0, 0.1, 0.0)


def test_at_most_three_routes_even_if_osrm_returns_four():
    distinct = [
        straight_route(100, hours, lon=-96 + offset)
        for offset, hours in enumerate([2, 2.2, 2.4, 2.6])
    ]
    with mock.patch.object(routing, "osrm_routes", return_value=distinct):
        routes = routing.get_route_options((30.0, -96.0), (31.4, -96.0))
    assert [round(r.path.duration_s / 3600, 1) for r in routes] == [2.0, 2.2, 2.4]


def test_single_route_is_planned_with_a_warning():
    with (
        mock.patch.object(planner, "get_route_options", return_value=[straight_route(50, 1)]),
        mock.patch.object(planner, "fetch_hourly", side_effect=calm_forecast),
    ):
        result = planner.plan_trip((30, -96), (30.7, -96), DEPART, 20_000, 25)
    assert result["recommended_route_id"] == "A"
    assert result["routes"][0]["why_not_recommended"] is None
    assert result["warnings"] == ["Only 1 distinct route(s) found."]


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"load_lbs": -1}, "load_lbs"),
        ({"load_lbs": 100_001}, "load_lbs"),
        ({"departure": (datetime.now(UTC) + timedelta(days=8)).isoformat()}, "departure"),
        ({"origin": {"lat": 91, "lon": 0}}, "origin"),
    ],
)
def test_out_of_range_input_is_rejected(overrides, field):
    body = {
        "origin": {"lat": 32.78, "lon": -96.80},
        "destination": {"lat": 29.76, "lon": -95.37},
        "departure": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "load_lbs": 42000,
        "interval_miles": 25,
    } | overrides
    response = Client().post("/api/plan", body, content_type="application/json")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert field in response.json()
