"""Dates/heures françaises ancrées au début métier de l'appel."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ABIDJAN = ZoneInfo("Africa/Abidjan")
HOURS = {
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "dix sept": 17,
    "dix huit": 18,
    "dix neuf": 19,
    "vingt": 20,
    "vingt et une": 21,
    "vingt deux": 22,
    "vingt trois": 23,
}
DAY_WORDS = {
    "premier": 1,
    "un": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "dix sept": 17,
    "dix huit": 18,
    "dix neuf": 19,
    "vingt": 20,
    "vingt et un": 21,
    "vingt deux": 22,
    "vingt trois": 23,
    "vingt quatre": 24,
    "vingt cinq": 25,
    "vingt six": 26,
    "vingt sept": 27,
    "vingt huit": 28,
    "vingt neuf": 29,
    "trente": 30,
    "trente et un": 31,
}


@dataclass(frozen=True)
class TemporalValue:
    normalized: str | None
    precision: str
    warning: str | None = None


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold().replace("-", " "))
    return " ".join("".join(c for c in normalized if not unicodedata.combining(c)).split())


def _base(reference: datetime) -> datetime:
    return (
        reference.replace(tzinfo=ABIDJAN)
        if reference.tzinfo is None
        else reference.astimezone(ABIDJAN)
    )


def _hour(value: str) -> tuple[int, int] | None:
    plain = _plain(value)
    if "minuit" in plain:
        return 0, 30 if "demi" in plain else 0
    if "midi" in plain:
        return 12, 30 if "demi" in plain else 0
    match = re.search(r"\b([01]?\d|2[0-3])\s*(?:heures?|h)(?:\s*([0-5]\d))?", plain)
    if match:
        return int(match.group(1)), int(match.group(2) or (30 if "demi" in plain else 0))
    for word, hour in sorted(HOURS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{word}\s+heures?\b", plain):
            if "soir" in plain and hour < 12:
                hour += 12
            return hour, 30 if "demi" in plain else 0
    return None


def parse_time(value: str, reference: datetime) -> TemporalValue:
    parsed = _hour(value)
    if parsed is None:
        return TemporalValue(None, "unparsed")
    hour, minute = parsed
    moment = _base(reference).replace(hour=hour, minute=minute, second=0, microsecond=0)
    approximate = bool(
        re.search(r"\b(vers|environ|environs|un peu avant|un peu apres)\b", _plain(value))
    )
    normalized_time = moment.isoformat().split("T", 1)[1]
    return TemporalValue(normalized_time, "approximate" if approximate else "exact")


def parse_date(value: str, reference: datetime) -> TemporalValue:
    plain = _plain(value)
    base = _base(reference)
    if "avant hier" in plain:
        return TemporalValue((base - timedelta(days=2)).date().isoformat(), "date_only")
    if "hier" in plain:
        return TemporalValue((base - timedelta(days=1)).date().isoformat(), "date_only")
    if "aujourd" in plain or "ce matin" in plain or "cet apres midi" in plain:
        return TemporalValue(base.date().isoformat(), "date_only")
    weekdays = {
        "lundi": 0,
        "mardi": 1,
        "mercredi": 2,
        "jeudi": 3,
        "vendredi": 4,
        "samedi": 5,
        "dimanche": 6,
    }
    for word, weekday in weekdays.items():
        if word in plain and ("dernier" in plain or "passe" in plain):
            days = (base.weekday() - weekday) % 7 or 7
            return TemporalValue((base - timedelta(days=days)).date().isoformat(), "date_only")
    prepared = plain
    for day_word, number in sorted(DAY_WORDS.items(), key=lambda item: len(item[0]), reverse=True):
        prepared = re.sub(rf"\b{day_word}\b", str(number), prepared, count=1)
        if prepared != plain:
            break
    from dateparser import parse as date_parse

    parsed = date_parse(
        prepared,
        languages=["fr"],
        settings={
            "RELATIVE_BASE": base,
            "TIMEZONE": "Africa/Abidjan",
            "PREFER_DATES_FROM": "past",
            "DATE_ORDER": "DMY",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if parsed is None:
        return TemporalValue(None, "unparsed")
    if parsed > base:
        return TemporalValue(parsed.date().isoformat(), "ambiguous", "future_date")
    return TemporalValue(parsed.date().isoformat(), "date_only")


def parse_datetime(value: str, reference: datetime) -> TemporalValue:
    date_value = parse_date(value, reference)
    time_value = parse_time(value, reference)
    if date_value.normalized is None and time_value.normalized is None:
        return TemporalValue(None, "unparsed")
    if date_value.normalized is None:
        return time_value
    if time_value.normalized is None:
        return date_value
    moment = datetime.fromisoformat(f"{date_value.normalized}T{time_value.normalized}")
    precision = "approximate" if time_value.precision == "approximate" else "exact"
    return TemporalValue(moment.isoformat(), precision, date_value.warning)
