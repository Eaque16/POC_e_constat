import httpx
import pytest

from econstat.config import Settings
from econstat.services.location import LocationResolver


class FakeGeocoder:
    def __init__(self, outcome):
        self.outcome = outcome

    def search(self, _query):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def reverse(self, _latitude, _longitude):
        return None


def candidate(place_id=1, name="Carrefour Siporex, Yopougon, Abidjan"):
    return {
        "place_id": place_id,
        "display_name": name,
        "lat": "5.345",
        "lon": "-4.076",
        "address": {"suburb": "Yopougon", "city": "Abidjan", "country": "Côte d'Ivoire"},
    }


def resolver(outcome):
    settings = Settings(disable_auth=True, geocoding_enabled=True)
    return LocationResolver(settings, FakeGeocoder(outcome))


def test_location_found_and_coordinates_only_come_from_provider():
    result = resolver([candidate()]).resolve("carrefour siporex yopougon")
    assert result["verification_status"] == "found"
    assert result["verified_in_gazetteer"] is True
    assert result["latitude"] == 5.345
    assert result["commune"] == "Yopougon"


def test_location_not_found_keeps_user_text_without_coordinates():
    result = resolver([]).resolve("repère synthétique")
    assert result["verification_status"] == "not_found"
    assert result["normalized"] == "repère synthétique"
    assert result["latitude"] is None


def test_location_ambiguous():
    result = resolver([candidate(1), candidate(2)]).resolve("Siporex")
    assert result["verification_status"] == "ambiguous"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (httpx.TimeoutException("timeout"), "timeout"),
        (httpx.ConnectError("offline"), "provider_unavailable"),
    ],
)
def test_location_provider_failures_are_degraded(error, status):
    assert resolver(error).resolve("Yopougon")["verification_status"] == status


def test_location_disabled_does_not_call_provider():
    settings = Settings(disable_auth=True, geocoding_enabled=False)
    result = LocationResolver(settings, FakeGeocoder(AssertionError("network"))).resolve("Yopougon")
    assert result["verification_status"] == "disabled"
