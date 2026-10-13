from planner.services.geo import METERS_PER_MILE
from planner.services.recommend import recommend, summarize
from planner.services.risk import Risk

MILE = METERS_PER_MILE


def route(route_id, hours, **miles):
    """Build a summary from miles per level, e.g. route("A", 5, low=90, severe=10)."""
    names = {
        "low": Risk.LOW,
        "moderate": Risk.MODERATE,
        "high": Risk.HIGH,
        "severe": Risk.SEVERE,
        "no_travel": Risk.NO_TRAVEL,
    }
    segments = [(names[k], v * MILE) for k, v in miles.items()]
    return summarize(route_id, segments, hours * 3600)


def test_summarize_miles_and_distance_weighted_average():
    s = summarize(
        "A", [(Risk.LOW, 50 * MILE), (Risk.HIGH, 25 * MILE), (Risk.SEVERE, 25 * MILE)], 3600
    )
    assert round(s.miles[Risk.HIGH], 6) == 25
    assert round(s.avg_risk, 6) == (0 * 50 + 2 * 25 + 3 * 25) / 100


def test_fewest_severe_miles_beats_faster_route():
    fast = route("A", 4, low=90, severe=10)
    slow = route("B", 6, low=80, high=20)
    ranked, reasons = recommend([fast, slow])
    assert ranked[0].route_id == "B"
    assert reasons == ["0 Severe miles vs 10 on Route A"]


def test_no_travel_route_never_wins_against_one_without():
    a = route("A", 4, low=99.9, no_travel=0.1)
    b = route("B", 9, low=20, severe=80)
    ranked, reasons = recommend([a, b])
    assert ranked[0].route_id == "B"
    assert a.has_no_travel and not b.has_no_travel
    assert reasons == ["avoids the 0.1 No Travel miles on Route A"]


def test_no_travel_miles_count_as_severe_when_every_route_has_some():
    a = route("A", 4, low=80, no_travel=5, severe=10)  # 15 severe-or-worse
    b = route("B", 5, low=80, no_travel=10)  # 10 severe-or-worse
    assert a.severe_miles == 15 and b.severe_miles == 10
    assert recommend([a, b])[0][0].route_id == "B"


def test_high_miles_break_severe_tie():
    a = route("A", 4, low=70, severe=10, high=20)
    b = route("B", 5, low=80, severe=10, high=10)
    assert recommend([a, b])[0][0].route_id == "B"


def test_average_risk_breaks_high_tie():
    a = route("A", 4, low=50, moderate=50)
    b = route("B", 5, low=90, moderate=10)
    ranked, reasons = recommend([a, b])
    assert ranked[0].route_id == "B"
    assert reasons[0].startswith("lower average risk than Route A")


def test_travel_time_is_final_tiebreaker():
    a = route("A", 5, low=100)
    b = route("B", 4, low=120)
    ranked, reasons = recommend([a, b])
    assert ranked[0].route_id == "B"
    assert reasons == ["faster than Route A (4h 00m vs 5h 00m)"]


def test_float_noise_does_not_decide_ranking():
    a = route("A", 4, low=100, severe=10.00001)
    b = route("B", 5, low=100, severe=10.0)
    assert recommend([a, b])[0][0].route_id == "A"  # equal severe miles -> faster wins
