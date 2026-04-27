from enum import Enum


class AutonomyLevel(Enum):
    FULLY_AUTONOMOUS = "auto"
    RECOMMEND = "recommend"
    ESCALATE = "escalate"
    HOLD = "hold"


class AutonomyEngine:
    def classify(self, reroute: dict) -> AutonomyLevel:
        cost_delta = abs(reroute.get("cost_delta_usd", 0))
        risk_reduction = reroute.get("old_risk", 0) - reroute.get("new_risk", 0)
        confidence = reroute.get("confidence", 0)

        if cost_delta <= 500 and risk_reduction >= 0.3 and confidence >= 0.90:
            return AutonomyLevel.FULLY_AUTONOMOUS
        if cost_delta <= 5_000 and confidence >= 0.75:
            return AutonomyLevel.RECOMMEND
        if cost_delta > 50_000 or confidence < 0.50:
            return AutonomyLevel.ESCALATE
        return AutonomyLevel.RECOMMEND
