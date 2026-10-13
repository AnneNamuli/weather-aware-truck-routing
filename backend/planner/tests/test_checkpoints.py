from datetime import UTC, datetime, timedelta

import pytest

from planner.services.checkpoints import (
    TimedPath,
    checkpoint_distances,
    coverage,
    sample_checkpoints,
)
from planner.services.geo import METERS_PER_MILE

MILE = METERS_PER_MILE
DEPART = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def straight_path(miles: float, hours: float) -> TimedPath:
    """Due-north line; distance and time grow linearly with latitude."""
    n = 11
    deg = miles * MILE / 111_195  # approx metres per degree latitude
    return TimedPath(
        points=[(i * deg / (n - 1), 0.0) for i in range(n)],
        cumulative_distance_m=[miles * MILE * i / (n - 1) for i in range(n)],
        cumulative_time_s=[hours * 3600 * i / (n - 1) for i in range(n)],
    )


def test_marks_include_origin_every_interval_and_destination():
    assert checkpoint_distances(100, 25) == [0, 25, 50, 75, 100]
    assert checkpoint_distances(110, 25) == [0, 25, 50, 75, 100, 110]


@pytest.mark.parametrize("total, interval", [(100, 25), (110, 25), (3, 10), (1234.5, 50)])
def test_coverage_sums_to_route_length(total, interval):
    marks = checkpoint_distances(total, interval)
    assert sum(coverage(marks)) == pytest.approx(total)


def test_coverage_is_half_gap_each_side():
    assert coverage([0, 25, 50, 60]) == [12.5, 25, 17.5, 5]


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_sample_checkpoints_eta_tracks_elapsed_time(interval):
    path = straight_path(miles=200, hours=4)  # 50 mph
    cps = sample_checkpoints(path, interval, DEPART)
    assert cps[0].eta == DEPART
    assert cps[-1].distance_m == pytest.approx(200 * MILE)
    assert cps[-1].eta == DEPART + timedelta(hours=4)
    for cp in cps:
        expected_hours = cp.distance_m / MILE / 50
        assert (cp.eta - DEPART).total_seconds() == pytest.approx(expected_hours * 3600, abs=1)
    assert sum(cp.covered_route_m for cp in cps) == pytest.approx(200 * MILE)


def test_eta_uses_uneven_segment_speeds():
    # First half (50 mi) takes 2 h, second half (50 mi) takes 30 min.
    path = TimedPath(
        points=[(0.0, 0.0), (0.72, 0.0), (1.44, 0.0)],
        cumulative_distance_m=[0, 50 * MILE, 100 * MILE],
        cumulative_time_s=[0, 7200, 9000],
    )
    cps = sample_checkpoints(path, 25, DEPART)
    elapsed = [cp.elapsed_s for cp in cps]
    assert elapsed == pytest.approx([0, 3600, 7200, 8100, 9000])
