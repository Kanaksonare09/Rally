import time
import math
from typing import List, Dict, Any
from apps.api.services.movement_service import MovementIntelligenceService
from apps.api.services.risk_service import RiskEngineService
from apps.api.services.recommendation_service import RecommendationEngineService

# Sample realistic route in Pacific Northwest Coast Highway
SAMPLE_ROUTE_WAYPOINTS = [
    [-122.3321, 47.6062], # Seattle, WA
    [-122.3350, 47.6100],
    [-122.3400, 47.6150],
    [-122.3480, 47.6200],
    [-122.3550, 47.6250],
    [-122.3600, 47.6300],
]

DEMO_MEMBERS = [
    {"id": "usr_alex", "name": "Alex (Leader)", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex"},
    {"id": "usr_ben", "name": "Ben", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Ben"},
    {"id": "usr_chloe", "name": "Chloe", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Chloe"},
    {"id": "usr_maya", "name": "Maya", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Maya"},
    {"id": "usr_david", "name": "David", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=David"},
    {"id": "usr_emma", "name": "Emma", "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Emma"},
]

class DemoGroupSimulator:
    def __init__(self):
        self.step_count = 0
        self.base_lat = 47.6062
        self.base_lng = -122.3321

    def get_simulation_step(self, step: int) -> Dict[str, Any]:
        """
        Generates deterministic moving group state for demo/testing.
        Simulates: Progress, Drifting (Chloe at step 4-8), Separation (David at step 9-12), SOS option.
        """
        self.step_count = step
        progress = (step % 20) * 0.0015 # Latitude offset

        # Base group position
        leader_lat = self.base_lat + progress
        leader_lng = self.base_lng + (progress * 0.5)

        member_locations = []

        for i, m in enumerate(DEMO_MEMBERS):
            m_id = m['id']
            # Default tight formation (10-30m spacing)
            offset_lat = (i * 0.0001)
            offset_lng = (i * 0.0001)
            speed = 13.5 # ~48 km/h
            connectivity = "ONLINE"

            # Simulate dynamic drifting behavior for Chloe (member 2)
            if m_id == "usr_chloe" and 4 <= step <= 8:
                offset_lat -= (step - 3) * 0.0006 # Falling behind
                speed = 8.0 # Slower speed

            # Simulate critical separation for David (member 4)
            elif m_id == "usr_david" and 9 <= step <= 13:
                offset_lat -= (step - 8) * 0.0012 # Falling significantly behind (>350m)
                speed = 4.0

            # Simulate temporary connectivity drop for Maya (member 3)
            elif m_id == "usr_maya" and step >= 14:
                connectivity = "OFFLINE"

            loc = {
                "user_id": m_id,
                "user_name": m['name'],
                "avatar_url": m['avatar'],
                "latitude": leader_lat + offset_lat,
                "longitude": leader_lng + offset_lng,
                "speed": speed,
                "heading": 45.0,
                "battery_level": max(0.2, 0.95 - (step * 0.01)),
                "connectivity_state": connectivity,
                "device_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            member_locations.append(loc)

        # Run intelligence detectors
        movement = MovementIntelligenceService.detect_drifting_and_separation(member_locations)
        route_devs = MovementIntelligenceService.detect_route_deviation(member_locations, SAMPLE_ROUTE_WAYPOINTS)
        offline_count = sum(1 for loc in member_locations if loc['connectivity_state'] == 'OFFLINE')
        offline_ids = [loc['user_id'] for loc in member_locations if loc['connectivity_state'] == 'OFFLINE']

        # Run Risk Engine
        risk = RiskEngineService.calculate_group_health(
            movement_analysis=movement,
            route_deviations=route_devs,
            offline_member_count=offline_count,
            total_member_count=len(DEMO_MEMBERS),
            active_sos=(step == 16) # Trigger SOS on step 16 for live demo testing
        )

        # Run Recommendation Engine
        recommendations = RecommendationEngineService.generate_recommendations(
            risk_assessment=risk,
            movement_analysis=movement,
            route_deviations=route_devs,
            offline_members=offline_ids
        )

        return {
            "step": step,
            "group_id": "grp_demo_rally",
            "trip_id": "trip_demo_coast_highway",
            "member_locations": member_locations,
            "movement_analysis": movement,
            "group_health": risk,
            "recommendations": recommendations,
            "route_waypoints": SAMPLE_ROUTE_WAYPOINTS
        }

simulator_instance = DemoGroupSimulator()
