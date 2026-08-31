"""Fournisseur géographique optionnel, borné par timeout et cache local."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

import httpx

from econstat.config import Settings


class Geocoder(Protocol):
    def search(self, query: str) -> list[dict]: ...

    def reverse(self, latitude: float, longitude: float) -> dict | None: ...


@dataclass
class _CacheEntry:
    expires_at: float
    value: object


class NominatimGeocoder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache: dict[tuple, _CacheEntry] = {}

    def _get(self, key: tuple):
        cached = self._cache.get(key)
        return cached.value if cached and cached.expires_at >= monotonic() else None

    def _put(self, key: tuple, value):
        self._cache[key] = _CacheEntry(
            monotonic() + self.settings.geocoding_cache_ttl_seconds, value
        )
        return value

    def search(self, query: str) -> list[dict]:
        key = ("search", query.casefold(), self.settings.geocoding_country_code)
        cached = self._get(key)
        if cached is not None:
            return cached
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 5,
                "countrycodes": self.settings.geocoding_country_code,
            },
            headers={"User-Agent": self.settings.geocoding_user_agent},
            timeout=self.settings.geocoding_timeout_seconds,
        )
        response.raise_for_status()
        return self._put(key, response.json())

    def reverse(self, latitude: float, longitude: float) -> dict | None:
        key = ("reverse", round(latitude, 5), round(longitude, 5))
        cached = self._get(key)
        if cached is not None:
            return cached
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1},
            headers={"User-Agent": self.settings.geocoding_user_agent},
            timeout=self.settings.geocoding_timeout_seconds,
        )
        response.raise_for_status()
        return self._put(key, response.json())
