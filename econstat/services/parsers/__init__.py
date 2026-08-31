"""Parsers déterministes spécialisés par slot métier."""

from econstat.services.parsers.datetime_parser import parse_date, parse_datetime, parse_time
from econstat.services.parsers.name_parser import parse_firstname, parse_lastname
from econstat.services.parsers.phone_parser import parse_phone
from econstat.services.parsers.plate_parser import parse_plate
from econstat.services.parsers.spelling_parser import parse_spelling
from econstat.services.parsers.yes_no_parser import parse_yes_no

__all__ = [
    "parse_date",
    "parse_datetime",
    "parse_firstname",
    "parse_lastname",
    "parse_phone",
    "parse_plate",
    "parse_spelling",
    "parse_time",
    "parse_yes_no",
]
