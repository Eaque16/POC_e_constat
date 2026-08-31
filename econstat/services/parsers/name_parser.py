"""Normalisation non destructive des noms et prénoms."""

import re

from econstat.services.parsers.spelling_parser import parse_spelling


def _normalize_name(value: str, *, spelling: bool = False) -> str | None:
    raw = value.strip()
    if spelling:
        return parse_spelling(raw)
    raw = re.sub(r"^(?:je m'appelle|mon nom est|c'est|moi c'est)\s+", "", raw, flags=re.I)
    raw = raw.replace("’", "'")
    if re.fullmatch(r"nguessan", raw, flags=re.I):
        raw = "N'Guessan"
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,80}", raw):
        return None
    parts = re.split(r"([ '-])", " ".join(raw.split()))
    return "".join(part if part in {" ", "'", "-"} else part.capitalize() for part in parts)


def parse_firstname(value: str, *, spelling: bool = False) -> str | None:
    return _normalize_name(value, spelling=spelling)


def parse_lastname(value: str, *, spelling: bool = False) -> str | None:
    normalized = _normalize_name(value, spelling=spelling)
    return normalized.upper() if normalized else None
