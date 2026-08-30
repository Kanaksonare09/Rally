"""
Group-level spatial analysis for one evaluation snapshot: which members'
locations are trustworthy right now, where the group's center is, how
spread out everyone is, and whether the group has split into clusters.

Pure/stateless — no Redis, no database, no memory of past evaluations.
Persistence/debounce for turning a *condition* into an *event* lives in
app/intelligence/detectors.py.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.intelligence.distance import Point, group_center, haversine_distance_meters, max_pairwise_distance_meters


@dataclass(frozen=True)
class MemberPosition:
    user_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float]
    movement_state: str  # "MOVING" | "STOPPED" | "STALE" | "OFFLINE"


@dataclass(frozen=True)
class MemberGroupAnalysis:
    user_id: str
    distance_from_center_meters: Optional[float]
    is_isolated: bool
    nearest_other_member_id: Optional[str]
    nearest_other_member_distance_meters: Optional[float]


@dataclass(frozen=True)
class GroupAnalysisResult:
    center: Optional[Point]
    eligible_member_ids: List[str]
    members: Dict[str, MemberGroupAnalysis]
    max_pairwise_distance_meters: float
    is_cohesive: bool
    # Distance-linked clusters, largest first. A single-cluster result
    # (len(clusters) <= 1) means the group hasn't split.
    clusters: List[List[str]] = field(default_factory=list)


def _is_usable(position: MemberPosition, min_accuracy_meters: float) -> bool:
    """Excludes members whose location shouldn't drive separation/
    isolation/center math: no fresh signal (STALE/OFFLINE — group center
    robustness section) or GPS too imprecise to trust (accuracy section)."""
    if position.movement_state not in ("MOVING", "STOPPED"):
        return False
    if position.accuracy is not None and position.accuracy > min_accuracy_meters:
        return False
    return True


def cluster_by_distance(positions: Sequence[MemberPosition], linkage_distance_meters: float) -> List[List[str]]:
    """Simple, explicitly non-ML clustering: two members are in the same
    cluster if they're within `linkage_distance_meters` of each other,
    transitively (union-find / connected components). Sufficient for
    "has the group split into meaningful clusters" without any of the
    false-positive risk of a flat "distance from center" check."""
    parent = {p.user_id: p.user_id for p in positions}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            d = haversine_distance_meters(
                positions[i].latitude, positions[i].longitude, positions[j].latitude, positions[j].longitude
            )
            if d <= linkage_distance_meters:
                union(positions[i].user_id, positions[j].user_id)

    groups: Dict[str, List[str]] = {}
    for p in positions:
        groups.setdefault(find(p.user_id), []).append(p.user_id)
    return sorted(groups.values(), key=len, reverse=True)


def analyze_group(
    positions: Sequence[MemberPosition],
    *,
    min_accuracy_meters: float,
    isolated_distance_meters: float,
    separation_distance_meters: float,
    cohesion_distance_meters: float,
) -> GroupAnalysisResult:
    usable = [p for p in positions if _is_usable(p, min_accuracy_meters)]
    center = group_center([(p.latitude, p.longitude) for p in usable])

    members: Dict[str, MemberGroupAnalysis] = {}
    for p in usable:
        dist_from_center = (
            haversine_distance_meters(p.latitude, p.longitude, center[0], center[1]) if center else None
        )

        nearest_id: Optional[str] = None
        nearest_dist: Optional[float] = None
        for other in usable:
            if other.user_id == p.user_id:
                continue
            d = haversine_distance_meters(p.latitude, p.longitude, other.latitude, other.longitude)
            if nearest_dist is None or d < nearest_dist:
                nearest_dist, nearest_id = d, other.user_id

        is_isolated = nearest_dist is not None and nearest_dist > isolated_distance_meters
        members[p.user_id] = MemberGroupAnalysis(
            user_id=p.user_id,
            distance_from_center_meters=dist_from_center,
            is_isolated=is_isolated,
            nearest_other_member_id=nearest_id,
            nearest_other_member_distance_meters=nearest_dist,
        )

    # Members with no usable location still get an entry (all-None) so
    # callers can build a complete per-member response without
    # special-casing "this member has no analysis at all".
    for p in positions:
        if p.user_id not in members:
            members[p.user_id] = MemberGroupAnalysis(
                user_id=p.user_id,
                distance_from_center_meters=None,
                is_isolated=False,
                nearest_other_member_id=None,
                nearest_other_member_distance_meters=None,
            )

    max_dist = max_pairwise_distance_meters([(p.latitude, p.longitude) for p in usable])
    clusters = cluster_by_distance(usable, separation_distance_meters)
    is_cohesive = max_dist <= cohesion_distance_meters if len(usable) >= 2 else True

    return GroupAnalysisResult(
        center=center,
        eligible_member_ids=[p.user_id for p in usable],
        members=members,
        max_pairwise_distance_meters=max_dist,
        is_cohesive=is_cohesive,
        clusters=clusters,
    )
