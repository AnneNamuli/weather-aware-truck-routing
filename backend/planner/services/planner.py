"""Routes -> checkpoints -> weather at ETA -> risk -> recommendation."""

from datetime import datetime, timedelta

from .checkpoints import sample_checkpoints
from .geo import METERS_PER_MILE, LatLon, simplify_indices
from .recommend import recommend, summarize
from .risk import Risk, assess
from .routing import get_route_options
from .weather import fetch_hourly

ROUTE_IDS = "ABC"
DISPLAY_TOLERANCE_DEG = 0.0002  # ~20 m
CORRIDOR_TOLERANCE_DEG = 0.02  # ~2 km, for the heatmap corridor


def _round(value: float, digits: int) -> float:
    """round() that never returns -0.0."""
    return round(value, digits) + 0.0  # avoids -0.0


def plan_trip(
    origin: LatLon,
    destination: LatLon,
    departure: datetime,
    load_lbs: float,
    interval_miles: int,
) -> dict:
    """Up to three routes with checkpoint weather and risk, and the recommended one."""
    route_options = get_route_options(origin, destination)
    checkpoints_by_route = [
        sample_checkpoints(option.path, interval_miles, departure) for option in route_options
    ]

    all_checkpoints = [checkpoint for route in checkpoints_by_route for checkpoint in route]
    latest_eta = max(route[-1].eta for route in checkpoints_by_route)
    forecasts = fetch_hourly(
        [checkpoint.position for checkpoint in all_checkpoints],
        departure,
        latest_eta + timedelta(hours=1),
    )
    conditions_at_checkpoint = {
        id(checkpoint): forecast.at(checkpoint.eta)
        for checkpoint, forecast in zip(all_checkpoints, forecasts, strict=True)
    }

    routes, summaries = [], []
    for route_id, option, checkpoints in zip(
        ROUTE_IDS, route_options, checkpoints_by_route, strict=False
    ):
        checkpoint_rows, risk_per_covered_length = [], []
        for checkpoint in checkpoints:
            conditions = conditions_at_checkpoint[id(checkpoint)]
            risk = assess(
                conditions.wind_mph, conditions.rain_in_hr, conditions.snow_in_hr, load_lbs
            )
            risk_per_covered_length.append((risk.level, checkpoint.covered_route_m))
            checkpoint_rows.append(
                {
                    "index": checkpoint.index,
                    "mile": _round(checkpoint.distance_m / METERS_PER_MILE, 1),
                    "covers_miles": _round(checkpoint.covered_route_m / METERS_PER_MILE, 2),
                    "lat": _round(checkpoint.position[0], 5),
                    "lon": _round(checkpoint.position[1], 5),
                    "eta": checkpoint.eta.isoformat(),
                    "elapsed_s": round(checkpoint.elapsed_s),
                    # Source precision. Rounding more could push a value over a threshold
                    # (0.496 in/hr snow is Low but would show as 0.5).
                    "wind_mph": _round(conditions.wind_mph, 1),
                    "gust_mph": _round(conditions.gust_mph, 1),
                    "rain_in_hr": _round(conditions.rain_in_hr, 3),
                    "snow_in_hr": _round(conditions.snow_in_hr, 3),
                    "risk": int(risk.level),
                    "risk_label": risk.level.label,
                    "levels": {
                        "wind": int(risk.wind_level),
                        "rain": int(risk.rain_level),
                        "snow": int(risk.snow_level),
                    },
                    "driver": risk.driver,
                    "load_note": risk.load_note,
                }
            )

        path = option.path
        summary = summarize(route_id, risk_per_covered_length, path.duration_s)
        summaries.append(summary)
        display_vertices = simplify_indices(path.points, DISPLAY_TOLERANCE_DEG)
        corridor_vertices = simplify_indices(path.points, CORRIDOR_TOLERANCE_DEG)
        routes.append(
            {
                "id": route_id,
                "roads": option.road_summary,
                "distance_miles": _round(path.distance_m / METERS_PER_MILE, 1),
                "duration_s": round(path.duration_s),
                "departure": departure.isoformat(),
                "arrival": (departure + timedelta(seconds=path.duration_s)).isoformat(),
                # [lat, lon, elapsed seconds]
                "geometry": [
                    [
                        _round(path.points[vertex][0], 5),
                        _round(path.points[vertex][1], 5),
                        round(path.cumulative_time_s[vertex]),
                    ]
                    for vertex in display_vertices
                ],
                "checkpoints": checkpoint_rows,
                "risk_miles": {
                    level.label: _round(miles, 1) for level, miles in summary.miles.items()
                },
                "avg_risk": _round(summary.avg_risk, 2),
                "has_no_travel": summary.has_no_travel,
                "corridor": [
                    [_round(path.points[vertex][0], 4), _round(path.points[vertex][1], 4)]
                    for vertex in corridor_vertices
                ],
            }
        )

    ranked, reasons = recommend(summaries)
    best = ranked[0]
    rank_by_route_id = {summary.route_id: rank for rank, summary in enumerate(ranked, start=1)}
    reason_by_route_id = {
        summary.route_id: f"Route {best.route_id} is recommended: {reason}"
        for summary, reason in zip(ranked[1:], reasons, strict=True)
    }
    for route in routes:
        route["rank"] = rank_by_route_id[route["id"]]
        route["why_not_recommended"] = reason_by_route_id.get(route["id"])

    warnings = []
    if len(routes) < len(ROUTE_IDS):
        warnings.append(f"Only {len(routes)} distinct route(s) found.")
    if best.miles[Risk.NO_TRAVEL] > 0:
        warnings.append("All routes hit No Travel conditions. Consider delaying departure.")
    elif best.miles[Risk.SEVERE] > 0:
        warnings.append("The recommended route still has Severe weather.")

    return {
        "departure": departure.isoformat(),
        "load_lbs": load_lbs,
        "interval_miles": interval_miles,
        "recommended_route_id": best.route_id,
        "recommendation_reasons": reasons,
        "warnings": warnings,
        "routes": routes,
    }
