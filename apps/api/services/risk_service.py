from typing import List, Dict, Any

class RiskEngineService:
    @staticmethod
    def calculate_group_health(
        movement_analysis: Dict[str, Any],
        route_deviations: List[Dict[str, Any]],
        offline_member_count: int,
        total_member_count: int,
        active_sos: bool = False
    ) -> Dict[str, Any]:
        """
        Computes dynamic Group Health score (0-100) and risk level with human-readable explanations.
        """
        if active_sos:
            return {
                "health_score": 15,
                "risk_level": "CRITICAL",
                "status_label": "CRITICAL_ALERT",
                "reasons": ["CRITICAL: Emergency SOS activated by group member."]
            }

        health = 100
        reasons = []

        drifting = movement_analysis.get("drifting_members", [])
        separated = movement_analysis.get("separated_members", [])
        max_spread = movement_analysis.get("max_group_spread_m", 0.0)

        # Deduce score for separated members
        if separated:
            health -= (len(separated) * 25)
            reasons.append(f"{len(separated)} member(s) critically separated (>350m).")

        # Deduce score for drifting members
        if drifting:
            health -= (len(drifting) * 12)
            reasons.append(f"{len(drifting)} member(s) drifting behind group.")

        # Deduce score for route deviation
        if route_deviations:
            health -= (len(route_deviations) * 15)
            reasons.append(f"{len(route_deviations)} member(s) deviated from planned route.")

        # Deduce score for offline members
        if offline_member_count > 0:
            health -= (offline_member_count * 10)
            reasons.append(f"{offline_member_count} member(s) currently offline.")

        # Large spread warning
        if max_spread > 500.0:
            health -= 10
            reasons.append(f"High group radius spread ({round(max_spread)}m).")

        # Bound health score between 0 and 100
        health_score = max(0, min(100, health))

        # Determine risk level category
        if health_score >= 85:
            risk_level = "LOW"
            status_label = "STABLE" if health_score < 95 else "OPTIMAL"
        elif health_score >= 65:
            risk_level = "MEDIUM"
            status_label = "MODERATE_RISK"
        elif health_score >= 40:
            risk_level = "HIGH"
            status_label = "HIGH_RISK"
        else:
            risk_level = "CRITICAL"
            status_label = "CRITICAL_ALERT"

        if not reasons:
            reasons.append("Group is moving in sync within safe parameters.")

        return {
            "health_score": health_score,
            "risk_level": risk_level,
            "status_label": status_label,
            "reasons": reasons
        }
