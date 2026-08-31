from __future__ import annotations

from rapidfuzz.fuzz import WRatio

from econstat.config import Settings
from econstat.services.geolocation import haversine_meters


def rank_candidate(
    query: str,
    candidate: dict,
    settings: Settings,
    *,
    lexicon_places: list[str],
    gps: tuple[float, float] | None = None,
) -> tuple[float, dict]:
    address = candidate.get("address") or {}
    label = str(candidate.get("display_name") or candidate.get("name") or "")
    lexical = WRatio(query.casefold(), label.casefold()) / 100
    commune_text = " ".join(
        str(address.get(key, "")) for key in ("suburb", "city_district", "town", "city")
    )
    commune = max(
        (
            WRatio(query.casefold(), item.casefold()) / 100
            for item in lexicon_places
            if item.casefold() in commune_text.casefold()
        ),
        default=0.0,
    )
    gazetteer = 1.0 if candidate.get("place_id") is not None else 0.0
    gps_score = 0.0
    distance_m = None
    try:
        latitude, longitude = float(candidate["lat"]), float(candidate["lon"])
        if gps:
            distance_m = haversine_meters(gps, (latitude, longitude))
            gps_score = max(0.0, 1.0 - distance_m / 50000)
    except (KeyError, TypeError, ValueError):
        latitude = longitude = None
    components = {"lexical": lexical, "commune": commune, "gazetteer": gazetteer, "gps": gps_score}
    score = (
        lexical * settings.location_lexical_weight
        + commune * settings.location_commune_weight
        + gazetteer * settings.location_gazetteer_weight
        + gps_score * settings.location_gps_weight
    )
    return round(score, 3), {
        **components,
        "distance_from_current_gps_m": round(distance_m) if distance_m is not None else None,
        "latitude": latitude,
        "longitude": longitude,
    }
