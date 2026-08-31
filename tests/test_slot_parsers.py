from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from econstat.services.parsers.datetime_parser import parse_date, parse_datetime, parse_time
from econstat.services.parsers.name_parser import parse_firstname, parse_lastname
from econstat.services.parsers.spelling_parser import parse_spelling

BASE = datetime(2026, 8, 29, 10, 0, tzinfo=ZoneInfo("Africa/Abidjan"))


@pytest.mark.parametrize(
    "name",
    [
        "Kouamelan",
        "N'Guessan",
        "Kouassi",
        "Yao",
        "Konan",
        "Koffi",
        "Traoré",
        "Ouattara",
        "Kouassi-Blaise",
    ],
)
def test_names_are_normalized_without_fuzzy_replacement(name):
    assert parse_firstname(name)
    assert parse_lastname(name)


def test_corrupted_name_is_not_replaced_by_another_plausible_name():
    assert parse_lastname("Kouasi") == "KOUASI"


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [("K O U A M E L A N", "KOUAMELAN"), ("N apostrophe G U E S S A N", "N'GUESSAN")],
)
def test_french_spelling(spoken, expected):
    assert parse_spelling(spoken) == expected


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("hier", "2026-08-28"),
        ("hier soir", "2026-08-28"),
        ("avant-hier", "2026-08-27"),
        ("le 28 août", "2026-08-28"),
        ("le vingt-huit août", "2026-08-28"),
        ("samedi dernier", "2026-08-22"),
    ],
)
def test_french_dates_are_relative_to_fixed_call_start(spoken, expected):
    assert parse_date(spoken, BASE).normalized == expected


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("huit heures du soir", "20:00:00+00:00"),
        ("8 heures 30", "08:30:00+00:00"),
        ("midi", "12:00:00+00:00"),
        ("midi et demi", "12:30:00+00:00"),
        ("minuit", "00:00:00+00:00"),
        ("vers 19 heures", "19:00:00+00:00"),
    ],
)
def test_french_times(spoken, expected):
    assert parse_time(spoken, BASE).normalized == expected


def test_combined_datetime_keeps_approximation():
    parsed = parse_datetime("hier vers huit heures du soir", BASE)
    assert parsed.normalized == "2026-08-28T20:00:00+00:00"
    assert parsed.precision == "approximate"
