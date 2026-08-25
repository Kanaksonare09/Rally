from typing import List, Dict, Any

class RecommendationEngineService:
    @staticmethod
    def generate_recommendations(
        risk_assessment: Dict[str, Any],
        movement_analysis: Dict[str, Any],
        route_deviations: List[Dict[str, Any]],
        offline_members: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generates deterministic, actionable group recommendations based on detected signals.
        """
        recommendations = []
        drifting = movement_analysis.get("drifting_members", [])
        separated = movement_analysis.get("separated_members", [])

        # Priority 1: Emergency / Critical Separation
        if separated:
            for s in separated:
                recommendations.append({
                    "priority": 1,
                    "action_text": f"Regroup immediately at next safe shoulder or landmark.",
                    "reason": f"Member distance ({s['distance_m']}m) has breached critical safety threshold."
                })

        # Priority 2: Drifting Members
        elif drifting:
            recommendations.append({
                "priority": 2,
                "action_text": "Reduce group lead speed by ~10%.",
                "reason": f"{len(drifting)} member(s) are falling behind the group centroid."
            })

        # Priority 3: Route Deviations
        if route_deviations:
            recommendations.append({
                "priority": 2,
                "action_text": "Check navigation track and return to planned route.",
                "reason": f"{len(route_deviations)} member(s) detected outside route buffer."
            })

        # Priority 4: Offline Members
        if offline_members:
            recommendations.append({
                "priority": 3,
                "action_text": "Attempt voice contact or verify network connectivity.",
                "reason": f"{len(offline_members)} member(s) lost cellular connectivity."
            })

        # Default Recommendation if green
        if not recommendations:
            recommendations.append({
                "priority": 4,
                "action_text": "Maintain current pace and route.",
                "reason": "All members are moving safely in tight formation."
            })

        return recommendations
