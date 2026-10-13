"""0-48 h weather grid over the trip corridor.

Rows are evenly spaced in Web-Mercator y so the frontend can stretch an nx x ny
image over the bounds and each pixel lands on its cell.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from .geo import LatLon, geodesic_distance_m, inverse_mercator_y, mercator_y
from .risk import assess
from .weather import fetch_hourly, floor_hour

HOURS = 48
MAX_CELLS = 220  # one forecast location each; Open-Meteo's free tier allows 600/min
MIN_BUFFER_M, MAX_BUFFER_M = 30_000, 120_000
BUFFER_SHARE_OF_DIAGONAL = 0.12
ROUTE_SAMPLES_PER_BUFFER = 3
STARTING_CELLS_ACROSS = 40
CELL_GROWTH_FACTOR = 1.12
M_PER_DEG_LAT = 111_320


@dataclass(frozen=True)
class CorridorGrid:
    """Grid cells near the routes. Row 0 is the northern edge."""

    west: float
    north_y: float  # Mercator y
    cell_size: float  # degrees of longitude (= Mercator y units)
    nx: int
    ny: int
    cells: list[int]  # row-major, row 0 = north; only cells near a route
    centers: list[LatLon]

    @property
    def bounds(self) -> list[list[float]]:
        """[[south, west], [north, east]] in degrees."""
        south = inverse_mercator_y(self.north_y - self.ny * self.cell_size)
        north = inverse_mercator_y(self.north_y)
        return [[south, self.west], [north, self.west + self.nx * self.cell_size]]


def _densify(line: list[LatLon], step_m: float) -> list[LatLon]:
    """The line with extra points so none are more than about `step_m` apart."""
    dense = [line[0]]
    for (start_lat, start_lon), (end_lat, end_lon) in pairwise(line):
        steps = max(
            1, math.ceil(geodesic_distance_m((start_lat, start_lon), (end_lat, end_lon)) / step_m)
        )
        for step in range(1, steps + 1):
            fraction = step / steps
            dense.append(
                (
                    start_lat + (end_lat - start_lat) * fraction,
                    start_lon + (end_lon - start_lon) * fraction,
                )
            )
    return dense


def corridor_grid(lines: list[list[LatLon]], max_cells: int = MAX_CELLS) -> CorridorGrid:
    """Grid over the routes' bounding box, keeping only cells near a route."""
    route_points = [point for line in lines for point in line]
    south = min(lat for lat, _ in route_points)
    north = max(lat for lat, _ in route_points)
    west = min(lon for _, lon in route_points)
    east = max(lon for _, lon in route_points)
    diagonal_m = geodesic_distance_m((south, west), (north, east))
    buffer_m = min(max(BUFFER_SHARE_OF_DIAGONAL * diagonal_m, MIN_BUFFER_M), MAX_BUFFER_M)

    lon_degree_scale = math.cos(math.radians((south + north) / 2))
    buffer_lat_deg = buffer_m / M_PER_DEG_LAT
    buffer_lon_deg = buffer_m / (M_PER_DEG_LAT * lon_degree_scale)
    west, east = west - buffer_lon_deg, east + buffer_lon_deg
    y_top, y_bottom = mercator_y(north + buffer_lat_deg), mercator_y(south - buffer_lat_deg)

    route_samples = [
        sample for line in lines for sample in _densify(line, buffer_m / ROUTE_SAMPLES_PER_BUFFER)
    ]

    def near_route(lat: float, lon: float) -> bool:
        """Within `buffer_m` of a route sample. Flat-earth distance is fine at this scale."""
        local_lon_scale = math.cos(math.radians(lat))
        buffer_deg_squared = buffer_lat_deg**2
        return any(
            (lat - sample_lat) ** 2 + ((lon - sample_lon) * local_lon_scale) ** 2
            <= buffer_deg_squared
            for sample_lat, sample_lon in route_samples
        )

    cell_size = max(east - west, y_top - y_bottom) / STARTING_CELLS_ACROSS
    while True:
        nx = math.ceil((east - west) / cell_size)
        ny = math.ceil((y_top - y_bottom) / cell_size)
        cells, centers = [], []
        for row in range(ny):
            lat = inverse_mercator_y(y_top - (row + 0.5) * cell_size)
            for col in range(nx):
                lon = west + (col + 0.5) * cell_size
                if near_route(lat, lon):
                    cells.append(row * nx + col)
                    centers.append((lat, lon))
        if len(cells) <= max_cells:
            return CorridorGrid(west, y_top, cell_size, nx, ny, cells, centers)
        cell_size *= CELL_GROWTH_FACTOR  # coarsen until the corridor fits in max_cells


def build_heatmap(lines: list[list[LatLon]], departure: datetime, load_lbs: float) -> dict:
    """Hourly weather and load-adjusted risk per corridor cell, 0-48 h after departure."""
    grid = corridor_grid(lines)
    start = floor_hour(departure)
    frames = HOURS + 2  # one extra so departure + 48 h is covered when departure isn't on the hour
    forecasts = fetch_hourly(grid.centers, start, start + timedelta(hours=frames - 1))

    layers: dict[str, list[list[float]]] = {
        "wind": [],
        "gust": [],
        "rain": [],
        "snow": [],
        "risk": [],
    }
    for hour in range(frames):
        layers["wind"].append([round(forecast.wind[hour], 1) for forecast in forecasts])
        layers["gust"].append([round(forecast.gust[hour], 1) for forecast in forecasts])
        layers["rain"].append([round(forecast.rain[hour], 3) for forecast in forecasts])
        layers["snow"].append([round(forecast.snow[hour], 3) for forecast in forecasts])
        layers["risk"].append(
            [
                int(
                    assess(
                        forecast.wind[hour], forecast.rain[hour], forecast.snow[hour], load_lbs
                    ).level
                )
                for forecast in forecasts
            ]
        )

    return {
        "hours": HOURS,
        "times": [(start + timedelta(hours=hour)).isoformat() for hour in range(frames)],
        "bounds": [[round(degrees, 5) for degrees in corner] for corner in grid.bounds],
        "nx": grid.nx,
        "ny": grid.ny,
        "cells": grid.cells,
        "layers": layers,
    }
