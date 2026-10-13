"""Route options from OSRM.

OSRM often returns fewer than three alternatives, so the rest come from routing
through detour points either side of the trip's midpoint.
"""

import logging
from dataclasses import dataclass
from http import HTTPStatus
from itertools import pairwise

from django.conf import settings

from .checkpoints import TimedPath
from .geo import METERS_PER_MILE, LatLon, cumulative, geodesic_distance_m, interpolate_along
from .upstream import UpstreamError, get_json

log = logging.getLogger(__name__)

ROUTE_COUNT = 3
MAX_DURATION_RATIO = 1.6  # relative to the fastest route
MAX_SHARED_FRACTION = 0.8
DETOUR_OFFSETS = (0.15, -0.15, 0.3, -0.3, 0.45, -0.45)  # x the trip's straight line
# For unreachable pairs OSRM snaps the point to the nearest *connected* road and still returns
# "Ok" (Kansas to France starts in Lisbon), so check how far it moved.
MAX_SNAP_M = 10_000
NO_ROAD_ROUTE = "No road route between these places."


@dataclass(frozen=True)
class RouteOption:
    """A route's timed path and its main road names."""

    path: TimedPath
    road_summary: str


def truck_segment_durations(distances_m: list[float], car_durations_s: list[float]) -> list[float]:
    """Car durations, slowed wherever the car would exceed the truck speed cap."""
    truck_max_speed_mps = settings.TRUCK_MAX_SPEED_MPH * METERS_PER_MILE / 3600
    return [
        max(car_s, distance_m / truck_max_speed_mps)
        for distance_m, car_s in zip(distances_m, car_durations_s, strict=True)
    ]


def _parse_route(route: dict) -> RouteOption:
    """Build a RouteOption with truck timings and road names from OSRM's JSON."""
    points: list[LatLon] = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    distances_m = [meters for leg in route["legs"] for meters in leg["annotation"]["distance"]]
    car_durations_s = [
        seconds for leg in route["legs"] for seconds in leg["annotation"]["duration"]
    ]
    if len(distances_m) != len(points) - 1:
        # No per-segment annotations: spread the total time over geometry distances.
        distances_m = [geodesic_distance_m(start, end) for start, end in pairwise(points)]
        total_m = sum(distances_m) or 1.0
        car_durations_s = [route["duration"] * meters / total_m for meters in distances_m]
    durations_s = truck_segment_durations(distances_m, car_durations_s)
    path = TimedPath(
        points=points,
        cumulative_distance_m=cumulative(distances_m),
        cumulative_time_s=cumulative(durations_s),
    )
    leg_summaries = [leg.get("summary", "") for leg in route["legs"]]
    road_names = [
        road.strip() for summary in leg_summaries for road in summary.split(",") if road.strip()
    ]
    return RouteOption(path=path, road_summary=", ".join(dict.fromkeys(road_names)))


def osrm_routes(waypoints: list[LatLon], alternatives: bool) -> list[RouteOption]:
    """Routes through `waypoints` from OSRM, with alternatives if asked for."""
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)
    params = {
        "overview": "full",
        "geometries": "geojson",
        "annotations": "distance,duration",
        "steps": "true",  # leg summaries (road names) need steps
        "alternatives": str(ROUTE_COUNT) if alternatives else "false",
    }
    try:
        data = get_json(
            f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}", params, service="Routing service"
        )
    except UpstreamError as exc:
        # OSRM answers 400 "NoRoute" when nothing connects the points (e.g. across an ocean).
        if exc.status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise UpstreamError(NO_ROAD_ROUTE, status=HTTPStatus.UNPROCESSABLE_ENTITY) from exc
        raise
    if data.get("code") != "Ok" or not data.get("routes"):
        raise UpstreamError(NO_ROAD_ROUTE, status=HTTPStatus.UNPROCESSABLE_ENTITY)
    _check_endpoints(data["waypoints"])
    return [_parse_route(route) for route in data["routes"]]


def _check_endpoints(waypoints: list[dict]) -> None:
    """Reject the route if OSRM moved its start or destination more than MAX_SNAP_M."""
    ends = (("start", "destination", waypoints[0]), ("destination", "start", waypoints[-1]))
    for this_end, other_end, waypoint in ends:
        snapped_m = waypoint["distance"]
        if snapped_m > MAX_SNAP_M:
            raise UpstreamError(
                f"{NO_ROAD_ROUTE} The nearest road that leads to the "
                f"{other_end} is {snapped_m / 1000:,.0f} km from the {this_end}, so they may "
                "be separated by sea.",
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )


class _CoverageIndex:
    """Grid of ~1 km cells touched by the accepted routes."""

    CELL_DEG = 0.01  # ~1.1 km

    def __init__(self):
        self.cells: set[tuple[int, int]] = set()

    def _cell_of(self, point: LatLon) -> tuple[int, int]:
        """Grid cell containing `point`."""
        lat, lon = point
        return int(lat // self.CELL_DEG), int(lon // self.CELL_DEG)

    def add(self, path: TimedPath):
        """Mark the cells along `path` and their neighbours."""
        for point in _resample(path, step_m=500):
            row, col = self._cell_of(point)
            for row_offset in (-1, 0, 1):
                for col_offset in (-1, 0, 1):
                    self.cells.add((row + row_offset, col + col_offset))

    def shared_fraction(self, path: TimedPath) -> float:
        """Share of `path` that runs along routes already added."""
        samples = _resample(path, step_m=1000)
        return sum(self._cell_of(sample) in self.cells for sample in samples) / len(samples)


def _resample(path: TimedPath, step_m: float) -> list[LatLon]:
    """Points about every `step_m` along the path, both ends included."""
    sample_count = max(2, int(path.distance_m // step_m) + 1)
    step = path.distance_m / (sample_count - 1)
    return [
        interpolate_along(path.points, path.cumulative_distance_m, step * i)[0]
        for i in range(sample_count)
    ]


def _detour_waypoints(origin: LatLon, destination: LatLon, fastest: TimedPath) -> list[LatLon]:
    """Points either side of the fastest route's midpoint, to force other routes."""
    midpoint_lat, midpoint_lon = interpolate_along(
        fastest.points, fastest.cumulative_distance_m, fastest.distance_m / 2
    )[0]
    # Step sideways: (lat, lon) -> (-lon, lat) is perpendicular to the trip's direction.
    # Rough in degrees, which is fine for picking detour points.
    trip_lat = destination[0] - origin[0]
    trip_lon = destination[1] - origin[1]
    return [
        (midpoint_lat - trip_lon * fraction, midpoint_lon + trip_lat * fraction)
        for fraction in DETOUR_OFFSETS
    ]


def get_route_options(origin: LatLon, destination: LatLon) -> list[RouteOption]:
    """Up to three distinct routes, fastest first."""
    candidates = osrm_routes([origin, destination], alternatives=True)
    fastest_s = candidates[0].path.duration_s
    accepted: list[RouteOption] = []
    covered = _CoverageIndex()

    def consider(option: RouteOption) -> None:
        """Accept `option` unless it is much slower or mostly duplicates an accepted route."""
        if option.path.duration_s > fastest_s * MAX_DURATION_RATIO:
            return
        if accepted and covered.shared_fraction(option.path) > MAX_SHARED_FRACTION:
            return
        accepted.append(option)
        covered.add(option.path)

    for option in candidates:
        consider(option)

    for via in _detour_waypoints(origin, destination, candidates[0].path):
        if len(accepted) >= ROUTE_COUNT:
            break
        try:
            consider(osrm_routes([origin, via, destination], alternatives=False)[0])
        except UpstreamError as exc:
            log.info("Detour via %s rejected: %s", via, exc)

    # OSRM can return a main route plus three alternatives; keep the three fastest.
    return sorted(accepted, key=lambda option: option.path.duration_s)[:ROUTE_COUNT]
