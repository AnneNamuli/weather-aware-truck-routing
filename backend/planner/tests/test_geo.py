import pytest

from planner.services.geo import (
    geodesic_distance_m,
    inverse_mercator_y,
    mercator_y,
    simplify_indices,
)

DALLAS = (32.7767, -96.7970)
HOUSTON = (29.7604, -95.3698)


def test_distance_matches_the_known_value():
    assert geodesic_distance_m(DALLAS, HOUSTON) == pytest.approx(361_000, rel=0.005)


def test_mercator_round_trips():
    assert inverse_mercator_y(mercator_y(47.6)) == pytest.approx(47.6)


def test_simplify_drops_points_within_tolerance_and_keeps_the_ends():
    nearly_straight = [(0, 0), (0.00001, 0.5), (0, 1), (1, 1)]
    assert simplify_indices(nearly_straight, 0.001) == [0, 2, 3]
    assert simplify_indices(nearly_straight, 0) == [0, 1, 2, 3]
    assert simplify_indices([(0, 0), (1, 1)], 0.5) == [0, 1]
