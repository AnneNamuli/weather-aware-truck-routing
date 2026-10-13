"""Place search via Photon (OpenStreetMap data, suitable for autocomplete)."""

from django.conf import settings
from django.core.cache import cache

from .upstream import get_json

CACHE_SECONDS = 24 * 3600


def _label(props: dict) -> str:
    """'Name, City, State, CC' without repeated parts."""
    parts = [props.get("name"), props.get("city"), props.get("state"), props.get("countrycode")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


def search(query: str, limit: int = 6) -> list[dict]:
    """Places matching `query` from Photon, cached for a day."""
    key = f"geo:{query.lower()}:{limit}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    data = get_json(
        f"{settings.PHOTON_BASE_URL}/api/",
        {"q": query, "limit": limit, "lang": "en"},
        service="Geocoding service",
    )
    results = []
    for feature in data.get("features", []):
        lon, lat = feature["geometry"]["coordinates"]
        label = _label(feature.get("properties", {}))
        if label:
            results.append({"label": label, "lat": round(lat, 6), "lon": round(lon, 6)})
    cache.set(key, results, CACHE_SECONDS)
    return results
