import pytest

from planner.services.risk import (
    Risk,
    apply_load_rules,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
)

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, L),
        (24.9, L),
        (25, M),
        (34.9, M),
        (35, H),
        (44.9, H),
        (45, S),
        (54.9, S),
        (55, N),
        (80, N),
    ],
)
def test_wind_bands(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.499, H),
        (0.50, S),
        (1.00, S),
        (1.001, N),
    ],
)
def test_rain_bands(rate, expected):
    assert classify_rain(rate) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N)],
)
def test_snow_bands(rate, expected):
    assert classify_snow(rate) == expected


@pytest.mark.parametrize(
    "mph, load, expected, escalated",
    [
        (55, 0, N, False),  # >=55 is No Travel for any load
        (50, 30_000, S, False),  # 45–54 needs load strictly over 30,000
        (50, 30_001, N, True),
        (45, 45_000, N, True),
        (40, 40_000, H, False),  # 35–44 needs load strictly over 40,000
        (40, 40_001, S, True),
        (35, 80_000, S, True),
        (34.9, 80_000, M, False),  # below 35 mph load does not matter
    ],
)
def test_load_rules(mph, load, expected, escalated):
    level, note = apply_load_rules(mph, load)
    assert level == expected
    assert (note is not None) == escalated


def test_assess_takes_worst_condition_and_names_drivers():
    a = assess(wind_mph=30, rain_in_hr=0.3, snow_in_hr=0.0, load_lbs=10_000)
    assert a.level == H
    assert a.drivers == ["rain"]

    tie = assess(wind_mph=40, rain_in_hr=0.3, snow_in_hr=0.0, load_lbs=10_000)
    assert tie.level == H
    assert tie.drivers == ["wind", "rain"]


def test_assess_heavy_load_escalates_overall_level():
    light = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lbs=20_000)
    heavy = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lbs=35_000)
    assert light.level == S and light.load_note is None
    assert heavy.level == N and heavy.load_note


def test_calm_weather_has_no_drivers():
    assert assess(5, 0, 0, 40_000).drivers == []
    assert assess(5, 0, 0, 40_000).driver == ""


def test_driver_label_names_load_rule():
    assert assess(40, 0, 0, 45_000).driver == "wind + load"  # High wind escalated to Severe by load
    assert assess(40, 0.3, 0, 10_000).driver == "wind, rain"
    assert assess(10, 0, 1.5, 80_000).driver == "snow"
