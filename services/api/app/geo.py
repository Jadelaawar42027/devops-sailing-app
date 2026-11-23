"""Small, pure geometry helpers."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_NM = 3440.065


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance in nautical miles."""
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlon = p2 - p1, radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * asin(min(1.0, sqrt(a)))
