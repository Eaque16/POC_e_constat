from econstat.services.geolocation import nearest_place


def test_nearest_place_uses_local_ivorian_reference():
    place, distance = nearest_place(5.36, -3.97)

    assert place == "Cocody"
    assert distance < 1
