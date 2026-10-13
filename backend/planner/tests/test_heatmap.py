from datetime import UTC, datetime
from unittest import mock

import pytest

from planner.services import heatmap
from planner.services.geo import geodesic_distance_m, inverse_mercator_y, mercator_y
from planner.services.weather import HourlySeries

ROUTE = [(32.78, -96.80), (31.5, -96.2), (29.76, -95.37)]  # roughly Dallas -> Houston
LONG_ROUTE = [(47.6, -122.3), (45.0, -110.0), (41.9, -87.6)]  # Seattle -> Chicago


@pytest.mark.parametrize("line", [ROUTE, LONG_ROUTE])
def test_grid_respects_cell_cap_and_covers_the_route(line):
    grid = heatmap.corridor_grid([line])
    assert 0 < len(grid.cells) <= heatmap.MAX_CELLS
    (south, west), (north, east) = grid.bounds
    for lat, lon in line:
        assert south < lat < north and west < lon < east


def test_cells_line_up_with_an_image_stretched_over_the_bounds():
    """The UI draws cell i as pixel (col, row) of an nx x ny image over `bounds`."""
    grid = heatmap.corridor_grid([ROUTE])
    (south, west), (north, east) = grid.bounds
    top, bottom = mercator_y(north), mercator_y(south)
    for cell, (lat, lon) in zip(grid.cells, grid.centers, strict=True):
        row, col = divmod(cell, grid.nx)
        assert lon == pytest.approx(west + (col + 0.5) * (east - west) / grid.nx)
        expected_lat = inverse_mercator_y(top - (row + 0.5) * (top - bottom) / grid.ny)
        assert lat == pytest.approx(expected_lat)


def test_only_cells_near_the_route_are_included():
    grid = heatmap.corridor_grid([ROUTE])
    assert len(grid.cells) < grid.nx * grid.ny
    far = max(min(geodesic_distance_m(c, p) for p in ROUTE) for c in grid.centers)
    assert far < 200_000  # buffer is at most 120 km plus densify/cell slack


def test_frames_cover_48h_after_an_off_the_hour_departure():
    def fake_forecast(points, start, end):
        hours = int((end - start).total_seconds() // 3600) + 1
        wind = [47.0] * hours
        zero = [0.0] * hours
        return [HourlySeries(start, wind, wind, zero, zero) for _ in points]

    departure = datetime(2026, 1, 1, 7, 30, tzinfo=UTC)
    with mock.patch.object(heatmap, "fetch_hourly", side_effect=fake_forecast):
        data = heatmap.build_heatmap([ROUTE], departure, load_lbs=35_000)

    assert data["hours"] == 48
    assert data["times"][0] == "2026-01-01T07:00:00+00:00"
    assert data["times"][-1] == "2026-01-03T08:00:00+00:00"  # >= departure + 48 h
    assert len(data["layers"]["risk"]) == len(data["times"])
    assert set(data["layers"]["risk"][0]) == {4}  # 47 mph + 35,000 lb -> No Travel


def test_displayed_values_agree_with_risk_near_a_threshold():
    """0.496 in/hr snow is Low; it must not be sent rounded to 0.5, which reads as Moderate."""

    def fake_forecast(points, start, end):
        hours = int((end - start).total_seconds() // 3600) + 1
        calm = [5.0] * hours
        return [HourlySeries(start, calm, calm, [0.0] * hours, [0.496] * hours) for _ in points]

    with mock.patch.object(heatmap, "fetch_hourly", side_effect=fake_forecast):
        data = heatmap.build_heatmap([ROUTE], datetime(2026, 1, 1, 7, tzinfo=UTC), load_lbs=0)

    assert set(data["layers"]["snow"][0]) == {0.496}
    assert set(data["layers"]["risk"][0]) == {0}
