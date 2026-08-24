"""Aide GPS locale limitée aux principales zones ivoiriennes du POC."""

from math import asin, cos, radians, sin, sqrt

PLACES = {
    "Abidjan": (5.3599, -4.0083),
    "Cocody": (5.3602, -3.9674),
    "Yopougon": (5.3364, -4.0712),
    "Marcory": (5.3027, -3.9827),
    "Treichville": (5.2937, -4.0094),
    "Plateau": (5.3267, -4.0217),
    "Adjamé": (5.3561, -4.0237),
    "Abobo": (5.4161, -4.0159),
    "Koumassi": (5.2975, -3.9569),
    "Port-Bouët": (5.2568, -3.9608),
    "Bingerville": (5.3558, -3.8854),
    "Yamoussoukro": (6.8276, -5.2893),
    "Bouaké": (7.6906, -5.0300),
    "San-Pédro": (4.7485, -6.6363),
    "Grand-Bassam": (5.2118, -3.7388),
    "Daloa": (6.8774, -6.4502),
    "Korhogo": (9.4580, -5.6296),
    "Man": (7.4125, -7.5538),
}


def nearest_place(latitude: float, longitude: float) -> tuple[str, float]:
    def distance(point: tuple[float, float]) -> float:
        lat1, lon1, lat2, lon2 = map(radians, (latitude, longitude, *point))
        delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
        value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        return 6371 * 2 * asin(sqrt(value))

    place, kilometers = min(
        ((place, distance(point)) for place, point in PLACES.items()),
        key=lambda item: item[1],
    )
    return place, round(kilometers, 1)
