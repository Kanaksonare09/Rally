"""
Live GPS-to-route matching: given a member's current (lat, lon) and a
route's planned geometry, find the nearest point *on* the route, how far
along the route that point is, and the distance the member currently sits
off the route line.

Deliberately pure Python (Shapely + Haversine), not a PostGIS
ST_LineLocatePoint/ST_ClosestPoint round trip per GPS update: a live trip
evaluates every member's position on every intelligence tick (every
INTELLIGENCE_EVALUATION_INTERVAL_SECONDS, see app/intelligence/engine.py)
— that's a query per member per tick, against a route that never changes
mid-trip. Loading the route's coordinates once (cached — see
app/route/service.py's geometry cache) and matching against them in memory
is both cheaper and, since this sandbox has no live PostGIS connection to
round-trip to anyway, the only thing that's actually testable here.

Accuracy: matching is per-segment (not whole-line-length-times-fraction).
Shapely does the planar nearest-point projection onto each individual
segment (fine at trip scale — a single segment spans meters to a few
kilometers, where the flat-earth approximation error is negligible); the
actual reported distances are always real-world meters via
app.intelligence.distance.haversine_distance_meters, never planar/degree
units. This avoids the common bug of approximating "distance traveled" as
`fraction_of_total_line_length * total_length` for a route whose segments
have very different real-world lengths per degree.

Coordinate convention: this module — like the `coordinates` column on
Route and every route/progress API payload — uses GeoJSON order
`[longitude, latitude]` for a coordinate pair (matching Shapely's own
(x, y) = (lon, lat) convention). This is the OPPOSITE order from
app.intelligence.distance.Point, which is (latitude, longitude). Every
function in this module takes latitude/longitude as separate named
arguments specifically to avoid that ambiguity at the call site.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from shapely.geometry import LineString, Point

from app.intelligence.distance import haversine_distance_meters

Coordinate = Tuple[float, float]  # (longitude, latitude) — GeoJSON order


@dataclass(frozen=True)
class RouteGeometry:
    """Precomputed once per route (cached — see app/route/service.py), then
    reused for every member's match on every evaluation tick."""

    coordinates: List[Coordinate]
    # cumulative_distances_meters[i] = real-world distance from
    # coordinates[0] to coordinates[i], walking the route.
    cumulative_distances_meters: List[float]
    total_distance_meters: float
    # One Shapely LineString per consecutive segment, built once so
    # matching never reconstructs geometry objects on the hot path.
    _segments: List[LineString]


@dataclass(frozen=True)
class RouteMatch:
    """One member's live position relative to the route, at one instant."""

    nearest_point: Tuple[float, float]  # (latitude, longitude) — app convention
    distance_from_route_meters: float
    route_fraction: float  # 0.0 (origin) .. 1.0 (destination)
    distance_traveled_meters: float
    distance_remaining_meters: float


def build_route_geometry(coordinates: Sequence[Sequence[float]]) -> RouteGeometry:
    """`coordinates` is the raw [[lon, lat], ...] list as stored on
    Route.coordinates. Raises ValueError for anything that can't form a
    real line (fewer than 2 points, or a degenerate/zero-length route)."""
    if len(coordinates) < 2:
        raise ValueError("A route needs at least 2 coordinates.")

    points: List[Coordinate] = [(float(c[0]), float(c[1])) for c in coordinates]

    cumulative = [0.0]
    segments: List[LineString] = []
    for i in range(len(points) - 1):
        lon1, lat1 = points[i]
        lon2, lat2 = points[i + 1]
        segment_length = haversine_distance_meters(lat1, lon1, lat2, lon2)
        cumulative.append(cumulative[-1] + segment_length)
        segments.append(LineString([points[i], points[i + 1]]))

    total = cumulative[-1]
    if total <= 0:
        raise ValueError("Route geometry has zero length — origin and destination coincide.")

    return RouteGeometry(
        coordinates=points, cumulative_distances_meters=cumulative, total_distance_meters=total, _segments=segments
    )


def match_point_to_route(geometry: RouteGeometry, latitude: float, longitude: float) -> RouteMatch:
    """Projects (latitude, longitude) onto the nearest point of the route's
    geometry. O(number of segments) — fine for the polyline lengths a
    planned trip route actually has; see this module's docstring for why
    that's an acceptable per-tick cost."""
    live_point = Point(longitude, latitude)  # Shapely wants (x, y) = (lon, lat)

    best_distance_meters = None
    best_traveled_meters = 0.0
    best_nearest_lat = geometry.coordinates[0][1]
    best_nearest_lon = geometry.coordinates[0][0]

    for i, segment in enumerate(geometry._segments):
        segment_length_planar = segment.length
        if segment_length_planar == 0:
            proj_lon, proj_lat = segment.coords[0]
            fraction_within_segment = 0.0
        else:
            proj_distance_planar = segment.project(live_point)
            proj_point = segment.interpolate(proj_distance_planar)
            proj_lon, proj_lat = proj_point.x, proj_point.y
            fraction_within_segment = min(1.0, max(0.0, proj_distance_planar / segment_length_planar))

        distance_meters = haversine_distance_meters(latitude, longitude, proj_lat, proj_lon)

        if best_distance_meters is None or distance_meters < best_distance_meters:
            segment_length_meters = (
                geometry.cumulative_distances_meters[i + 1] - geometry.cumulative_distances_meters[i]
            )
            best_distance_meters = distance_meters
            best_traveled_meters = geometry.cumulative_distances_meters[i] + fraction_within_segment * segment_length_meters
            best_nearest_lat, best_nearest_lon = proj_lat, proj_lon

    total = geometry.total_distance_meters
    traveled = min(total, max(0.0, best_traveled_meters))
    remaining = total - traveled

    return RouteMatch(
        nearest_point=(best_nearest_lat, best_nearest_lon),
        distance_from_route_meters=best_distance_meters or 0.0,
        route_fraction=traveled / total if total > 0 else 0.0,
        distance_traveled_meters=traveled,
        distance_remaining_meters=remaining,
    )
