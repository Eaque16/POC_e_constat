"""Résolution locale puis géographique d'un lieu prononcé."""

from __future__ import annotations

import httpx

from econstat.config import Settings
from econstat.services.confidence import composite_confidence
from econstat.services.lexicon import LocalLexicon
from econstat.services.location.geocoder import Geocoder, NominatimGeocoder
from econstat.services.location.location_ranker import rank_candidate


class LocationResolver:
    def __init__(self, settings: Settings, geocoder: Geocoder | None = None):
        self.settings = settings
        self.lexicon = LocalLexicon(settings.lexicon_path)
        self.geocoder = geocoder or NominatimGeocoder(settings)

    def resolve(
        self,
        transcript: str,
        *,
        gps: tuple[float, float] | None = None,
        asr_confidence: float = 0.75,
    ) -> dict:
        local = self.lexicon.correct_place(transcript, threshold=88)
        status = "disabled"
        candidates: list[dict] = []
        if self.settings.geocoding_enabled:
            try:
                raw_candidates = self.geocoder.search(local)
                status = "not_found" if not raw_candidates else "found"
                for candidate in raw_candidates:
                    score, components = rank_candidate(
                        local,
                        candidate,
                        self.settings,
                        lexicon_places=self.lexicon.entries.get("lieux", []),
                        gps=gps,
                    )
                    candidates.append({**candidate, "score": score, "score_components": components})
                candidates.sort(key=lambda item: item["score"], reverse=True)
                if len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] < 0.08:
                    status = "ambiguous"
            except httpx.TimeoutException:
                status = "timeout"
            except (httpx.HTTPError, OSError):
                status = "provider_unavailable"
        top = candidates[0] if candidates else None
        address = (top or {}).get("address") or {}
        components = {
            "asr": asr_confidence,
            "lexical": (top or {})
            .get("score_components", {})
            .get("lexical", 0.5 if local else 0.0),
            "gazetteer": 1.0 if top else 0.0,
            "ambiguity": 0.5 if status == "ambiguous" else 1.0,
            "confirmation": 0.0,
        }
        normalized = (top or {}).get("display_name") or local or None
        return {
            "slot": "location",
            "raw_transcript": transcript,
            "normalized": normalized,
            "commune": address.get("suburb") or address.get("city_district") or address.get("town"),
            "city": address.get("city") or address.get("municipality"),
            "country": address.get("country"),
            "latitude": (top or {}).get("score_components", {}).get("latitude"),
            "longitude": (top or {}).get("score_components", {}).get("longitude"),
            "provider": self.settings.geocoding_provider if top else None,
            "provider_id": str(top.get("place_id"))
            if top and top.get("place_id") is not None
            else None,
            "verified_in_gazetteer": bool(top),
            "verification_status": status,
            "confidence": composite_confidence(components),
            "confidence_components": components,
            "confirmed": False,
            "source": "voice",
            "parser": "location_resolver",
            "evidence": transcript,
            "metadata": {
                "candidates": candidates[:3],
                "gps_is_current_position_only": gps is not None,
            },
        }
