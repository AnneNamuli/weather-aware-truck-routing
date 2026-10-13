from http import HTTPStatus
from unittest import mock

import pytest
from django.test import override_settings

from planner.services import routing
from planner.services.checkpoints import TimedPath
from planner.services.geo import METERS_PER_MILE, cumulative
from planner.services.routing import RouteOption, get_route_options, truck_segment_durations


def option(points, hours) -> RouteOption:
    seg = [1000.0] * (len(points) - 1)
    total = hours * 3600
    return RouteOption(
        path=TimedPath(points, cumulative(seg), cumulative([total / len(seg)] * len(seg))),
        road_summary="",
    )


def line(lon, n=60, lat0=30.0, lat1=31.0):
    return [(lat0 + (lat1 - lat0) * i / (n - 1), lon) for i in range(n)]


@override_settings(TRUCK_MAX_SPEED_MPH=60)
def test_truck_speed_cap_only_slows_fast_segments():
    mile = METERS_PER_MILE
    # 1 mile in 40 s (90 mph) -> capped to 60 s; 1 mile in 120 s (30 mph) unchanged.
    assert truck_segment_durations([mile, mile], [40, 120]) == pytest.approx([60, 120])


def test_overlapping_alternatives_are_dropped_and_detours_fill_to_three():
    primary = option(line(-96.0), 4)
    duplicate = option(line(-96.0), 4.1)  # same road
    detours = iter([option(line(-95.5), 5), option(line(-96.5), 5.5)])

    def fake_osrm(waypoints, alternatives):
        return [primary, duplicate] if alternatives else [next(detours)]

    with mock.patch.object(routing, "osrm_routes", side_effect=fake_osrm):
        routes = get_route_options((30.0, -96.0), (31.0, -96.0))

    assert [r.path.duration_s for r in routes] == pytest.approx([4 * 3600, 5 * 3600, 5.5 * 3600])


def test_detours_much_slower_than_fastest_are_rejected():
    primary = option(line(-96.0), 4)

    def fake_osrm(waypoints, alternatives):
        return [primary] if alternatives else [option(line(-95.0), 7)]  # 1.75x

    with mock.patch.object(routing, "osrm_routes", side_effect=fake_osrm):
        assert len(get_route_options((30.0, -96.0), (31.0, -96.0))) == 1


def osrm_response(origin_snap_m: float, destination_snap_m: float) -> dict:
    coords = [[-96.0, 30.0], [-96.0, 31.0]]
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": {"coordinates": coords},
                "legs": [
                    {"summary": "I 45", "annotation": {"distance": [111_000], "duration": [4000]}}
                ],
                "duration": 4000,
            }
        ],
        "waypoints": [{"distance": origin_snap_m}, {"distance": destination_snap_m}],
    }


def test_route_from_a_moved_origin_is_rejected():
    """Kansas -> France: OSRM moves the origin to Lisbon (7,799 km) and still says "Ok"."""
    with (
        mock.patch.object(routing, "get_json", return_value=osrm_response(7_798_628, 0.3)),
        pytest.raises(
            routing.UpstreamError, match="leads to the destination is 7,799 km from the start"
        ) as err,
    ):
        routing.osrm_routes([(37.44, -98.42), (50.56, 2.83)], alternatives=True)
    assert err.value.status == HTTPStatus.UNPROCESSABLE_ENTITY


def test_small_snaps_to_the_nearest_road_are_fine():
    with mock.patch.object(routing, "get_json", return_value=osrm_response(43, 2_500)):
        [route] = routing.osrm_routes([(30.0, -96.0), (31.0, -96.0)], alternatives=True)
    assert route.road_summary == "I 45"


def test_detour_points_sit_either_side_of_the_midpoint():
    northbound = option(line(-96.0), 4)  # due north from (30, -96) to (31, -96)
    points = routing._detour_waypoints((30.0, -96.0), (31.0, -96.0), northbound.path)
    midpoint_lat = points[0][0]
    assert all(lat == pytest.approx(midpoint_lat) for lat, _ in points)  # sideways only
    longitudes = [lon for _, lon in points]
    assert min(longitudes) < -96.0 < max(longitudes)  # some west, some east


def test_osrm_no_route_gets_the_same_message_as_a_far_snap():
    """Honolulu to Los Angeles: OSRM itself refuses with 400 NoRoute."""
    refusal = routing.UpstreamError(
        "Routing service error: Impossible route", HTTPStatus.UNPROCESSABLE_ENTITY
    )
    with (
        mock.patch.object(routing, "get_json", side_effect=refusal),
        pytest.raises(
            routing.UpstreamError, match=r"^No road route between these places\.$"
        ) as err,
    ):
        routing.osrm_routes([(21.3, -157.9), (34.1, -118.2)], alternatives=True)
    assert err.value.status == HTTPStatus.UNPROCESSABLE_ENTITY
