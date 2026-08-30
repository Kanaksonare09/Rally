"""
Geographic distance calculations for live (in-memory) intelligence
calculations. Deliberately NOT a database call — every live evaluation
already has member coordinates from Redis, and round-tripping to Postgres
just to compute ST_Distance on the same numbers would be pure overhead.
PostGIS remains the right tool for anything that needs to query
location_history itself (spatial indexes, historical routes) — that's a
later phase's concern, not this one's.

Haversine, not Euclidean-on-raw-lat/lon: degrees of longitude cover very
different real-world distances depending on latitude, so naive Euclidean
distance on (lat, lon) pairs is wrong by a latitude-dependent factor
almost everywhere on Earth.
"""

import math
from typing import List, Optional, Sequence, Tuple

EARTH_RADIUS_METERS = 6_371_000.0

Point = Tuple[float, float]  # (latitude, longitude)


def _validate_point(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Invalid latitude: {lat!r}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Invalid longitude: {lon!r}")
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        raise ValueError(f"Non-finite coordinate: ({lat!r}, {lon!r})")


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in meters. Raises
    ValueError on invalid (NaN/out-of-range) coordinates rather than
    silently returning a meaningless number."""
    _validate_point(lat1, lon1)
    _validate_point(lat2, lon2)

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    a = min(1.0, max(0.0, a))  # clamp for float rounding right at antipodal points
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_METERS * c


def group_center(points: Sequence[Point]) -> Optional[Point]:
    """Arithmetic mean of latitude/longitude — the simple, documented
    first implementation (see app/intelligence/group_analysis.py for
    where outlier/staleness filtering happens *before* points reach here;
    this function trusts whatever it's given).

    Good enough for a tightly-clustered group over a small area. A real
    geographic centroid (accounting for the sphere) would matter at much
    larger scales than a group trip ever spans — noted as the upgrade
    path, not implemented here per this phase's explicit scope.
    """
    if not points:
        return None
    lat_sum = sum(p[0] for p in points)
    lon_sum = sum(p[1] for p in points)
    n = len(points)
    return (lat_sum / n, lon_sum / n)


def max_pairwise_distance_meters(points: Sequence[Point]) -> float:
    """The largest distance between any two points in the set — a simple,
    cheap cohesion signal (used by MOVING_TOGETHER / group separation).
    O(n^2), which is fine for group sizes RALLY actually expects (a
    handful to a few dozen members, not thousands)."""
    if len(points) < 2:
        return 0.0
    max_dist = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = haversine_distance_meters(points[i][0], points[i][1], points[j][0], points[j][1])
            if d > max_dist:
                max_dist = d
    return max_dist
