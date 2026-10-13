"""Checkpoints every N miles along a route, with ETAs.

Each checkpoint covers half the gap to each neighbour, so covered miles add up
to the route length.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .geo import METERS_PER_MILE, LatLon, interpolate_along

FLOAT_TOLERANCE_M = 1e-6


@dataclass(frozen=True)
class TimedPath:
    """Polyline plus distance (m) and drive time (s) from the start to each vertex."""

    points: list[LatLon]
    cumulative_distance_m: list[float]
    cumulative_time_s: list[float]

    @property
    def distance_m(self) -> float:
        """Route length in meters."""
        return self.cumulative_distance_m[-1]

    @property
    def duration_s(self) -> float:
        """Drive time in seconds."""
        return self.cumulative_time_s[-1]

    def elapsed_at(self, distance_m: float) -> float:
        """Drive time in seconds to reach `distance_m`, linear within a segment."""
        if len(self.points) < 2:
            return 0.0
        _, segment, fraction = interpolate_along(
            self.points, self.cumulative_distance_m, distance_m
        )
        segment_start_s = self.cumulative_time_s[segment]
        segment_end_s = self.cumulative_time_s[segment + 1]
        return segment_start_s + (segment_end_s - segment_start_s) * fraction


@dataclass(frozen=True)
class Checkpoint:
    """A weather sampling point on a route."""

    index: int
    distance_m: float
    position: LatLon
    elapsed_s: float
    eta: datetime
    covered_route_m: float


def checkpoint_distances(total_m: float, interval_m: float) -> list[float]:
    """Checkpoint distances in meters: 0, every `interval_m`, and the destination."""
    if interval_m <= 0:
        raise ValueError("interval must be positive")
    distances = []
    distance = 0.0
    while distance < total_m - FLOAT_TOLERANCE_M:
        distances.append(distance)
        distance += interval_m
    distances.append(total_m)
    return distances


def coverage(distances: list[float]) -> list[float]:
    """Half the gap to each neighbour."""
    if len(distances) == 1:
        return [0.0]
    covered = []
    last = len(distances) - 1
    for index, distance in enumerate(distances):
        covers_from = distance if index == 0 else (distances[index - 1] + distance) / 2
        covers_to = distance if index == last else (distance + distances[index + 1]) / 2
        covered.append(covers_to - covers_from)
    return covered


def sample_checkpoints(
    path: TimedPath, interval_miles: float, departure: datetime
) -> list[Checkpoint]:
    """Checkpoints every `interval_miles` along `path`, with ETAs from `departure`."""
    distances = checkpoint_distances(path.distance_m, interval_miles * METERS_PER_MILE)
    checkpoints = []
    for index, (distance_m, covered_route_m) in enumerate(
        zip(distances, coverage(distances), strict=True)
    ):
        position, _, _ = interpolate_along(path.points, path.cumulative_distance_m, distance_m)
        elapsed_s = path.elapsed_at(distance_m)
        checkpoints.append(
            Checkpoint(
                index=index,
                distance_m=distance_m,
                position=position,
                elapsed_s=elapsed_s,
                eta=departure + timedelta(seconds=elapsed_s),
                covered_route_m=covered_route_m,
            )
        )
    return checkpoints
