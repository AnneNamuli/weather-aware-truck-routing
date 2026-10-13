"""Geometry helpers. Coordinates are (lat, lon) tuples in degrees."""

import math
from bisect import bisect_right

from geopy.distance import geodesic
from shapely import LineString

METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def geodesic_distance_m(start: LatLon, end: LatLon) -> float:
    """Distance in meters on the earth's surface (geopy, WGS84)."""
    return geodesic(start, end).meters


def cumulative(values: list[float]) -> list[float]:
    """Running totals starting at 0: [a, b] gives [0, a, a + b]."""
    running_totals = [0.0]
    for value in values:
        running_totals.append(running_totals[-1] + value)
    return running_totals


def interpolate_along(
    points: list[LatLon], cumulative: list[float], target: float
) -> tuple[LatLon, int, float]:
    """Point at `target` along the polyline, where `cumulative` is distance or time per
    vertex. Returns (point, segment index, fraction along the segment)."""
    if target <= cumulative[0]:
        return points[0], 0, 0.0
    if target >= cumulative[-1]:
        return points[-1], len(points) - 2, 1.0
    segment = bisect_right(cumulative, target) - 1
    segment_length = cumulative[segment + 1] - cumulative[segment]
    fraction = 0.0 if segment_length <= 0 else (target - cumulative[segment]) / segment_length
    (start_lat, start_lon), (end_lat, end_lon) = points[segment], points[segment + 1]
    point = (
        start_lat + (end_lat - start_lat) * fraction,
        start_lon + (end_lon - start_lon) * fraction,
    )
    return point, segment, fraction


def mercator_y(lat: float) -> float:
    """Web-Mercator y in 'degree' units (same scale as longitude)."""
    lat = max(min(lat, 85.0), -85.0)
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def inverse_mercator_y(y: float) -> float:
    """Latitude for a Web-Mercator y."""
    return math.degrees(2 * math.atan(math.exp(math.radians(y))) - math.pi / 2)


def simplify_indices(points: list[LatLon], tolerance_deg: float) -> list[int]:
    """Indices of the points kept when simplifying the line (shapely, Douglas-Peucker)."""
    if len(points) <= 2:
        return list(range(len(points)))
    # Carry each point's index as z; shapely keeps it on the points it doesn't drop.
    line = LineString([(lon, lat, index) for index, (lat, lon) in enumerate(points)])
    simplified = line.simplify(tolerance_deg, preserve_topology=False)
    return [int(index) for _, _, index in simplified.coords]
