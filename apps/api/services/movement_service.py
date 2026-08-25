import math
from typing import List, Dict, Any, Optional

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates Haversine distance in meters between two lat/lng coordinates."""
    R = 6371000.0  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class MovementIntelligenceService:
    @staticmethod
    def calculate_group_centroid(member_locations: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        if not member_locations:
            return None
        total_lat = sum(loc['latitude'] for loc in member_locations)
        total_lng = sum(loc['longitude'] for loc in member_locations)
        n = len(member_locations)
        return {"latitude": total_lat / n, "longitude": total_lng / n}

    @staticmethod
    def detect_drifting_and_separation(
        member_locations: List[Dict[str, Any]],
        safe_threshold: float = 150.0,
        drifting_threshold: float = 250.0,
        critical_threshold: float = 350.0
    ) -> Dict[str, Any]:
        """
        Evaluates member distance relative to group centroid and pairwise distances.
        Categorizes states: SAFE, DRIFTING, SEPARATION RISK, SEPARATED.
        """
        centroid = MovementIntelligenceService.calculate_group_centroid(member_locations)
        if not centroid:
            return {
                "drifting_members": [],
                "separated_members": [],
                "member_distances": {},
                "max_group_spread_m": 0.0
            }

        drifting_members = []
        separated_members = []
        member_distances = {}
        max_spread = 0.0

        for loc in member_locations:
            u_id = loc['user_id']
            dist = haversine_distance(
                centroid['latitude'], centroid['longitude'],
                loc['latitude'], loc['longitude']
            )
            member_distances[u_id] = round(dist, 1)

            if dist > critical_threshold:
                separated_members.append({
                    "user_id": u_id,
                    "distance_m": round(dist, 1),
                    "status": "SEPARATED"
                })
            elif dist > drifting_threshold:
                drifting_members.append({
                    "user_id": u_id,
                    "distance_m": round(dist, 1),
                    "status": "DRIFTING"
                })

        # Calculate maximum pairwise distance (group radius spread)
        for i in range(len(member_locations)):
            for j in range(i + 1, len(member_locations)):
                d = haversine_distance(
                    member_locations[i]['latitude'], member_locations[i]['longitude'],
                    member_locations[j]['latitude'], member_locations[j]['longitude']
                )
                if d > max_spread:
                    max_spread = d

        return {
            "drifting_members": drifting_members,
            "separated_members": separated_members,
            "member_distances": member_distances,
            "max_group_spread_m": round(max_spread, 1),
            "centroid": centroid
        }

    @staticmethod
    def detect_route_deviation(
        member_locations: List[Dict[str, Any]],
        planned_waypoints: List[List[float]], # [[lng, lat], ...]
        deviation_threshold_m: float = 100.0
    ) -> List[Dict[str, Any]]:
        """Compares member positions against planned route segments."""
        if not planned_waypoints or len(planned_waypoints) < 2:
            return []

        deviated_members = []
        for loc in member_locations:
            min_dist = float('inf')
            u_lat = loc['latitude']
            u_lng = loc['longitude']

            # Minimum distance to any route waypoint point
            for wp in planned_waypoints:
                wp_lng, wp_lat = wp[0], wp[1]
                dist = haversine_distance(u_lat, u_lng, wp_lat, wp_lng)
                if dist < min_dist:
                    min_dist = dist

            if min_dist > deviation_threshold_m:
                deviated_members.append({
                    "user_id": loc['user_id'],
                    "distance_off_route_m": round(min_dist, 1)
                })

        return deviated_members
