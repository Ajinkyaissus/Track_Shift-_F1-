"""
TrackShift — Driver & Race Engineer Operational Radio Advisory Engine
=====================================================================
Generates concise, evidence-based, operationally actionable radio recommendations
for race engineers and drivers from real telemetry debt, trend, cliff risk,
and pit window calculations.

Rules:
- Concise, clear operational communication
- Identify action, timing, reason, and confidence status
- Strictly avoid unsupported certainty ("You must pit", "Guaranteed fastest", "Tyre will fail")
- 100% computed from authentic telemetry values (no hardcoded demos)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DriverAdvisoryResponse:
    """Machine-readable operational driver radio advisory."""
    action: str                        # "PIT", "STAY_OUT", "PREPARE_PIT", "HOLD_STRATEGY"
    target_lap: Optional[int]          # Recommended pit lap or None
    advisory_text: str                 # Operational radio message
    reason_codes: List[str]            # Machine-readable trigger reasons
    confidence_status: str             # "HIGHER SUPPORT", "CONDITIONAL", "LIMITED", "INSUFFICIENT DATA"
    model_status: str                  # "STAGE2_PRODUCTION"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "target_lap": self.target_lap,
            "advisory_text": self.advisory_text,
            "reason_codes": self.reason_codes,
            "confidence_status": self.confidence_status,
            "model_status": self.model_status,
            "details": self.details,
        }


def generate_driver_advisory(
    current_lap: int,
    tyre_age: int,
    cumulative_debt: float,
    debt_trend: float = 0.0,
    degradation_state: str = "NOMINAL",
    cliff_risk: float = 0.1,
    earliest_forced_pit: int = 15,
    optimal_pit: int = 20,
    latest_safe_pit: int = 25,
    future_forecast_loss_h5: float = 0.4,
    competitor_threat: str = "LOW",
    sample_count: int = 20,
    model_status: str = "STAGE2_PRODUCTION",
) -> DriverAdvisoryResponse:
    """
    Computes a concise driver/race-engineer advisory based on real telemetry metrics.
    """
    reason_codes = []
    
    # 1. Determine confidence/evidence status
    if sample_count < 3:
        confidence_status = "INSUFFICIENT DATA"
    elif sample_count < 8:
        confidence_status = "LIMITED"
    elif sample_count >= 20 and degradation_state != "CRITICAL":
        confidence_status = "HIGHER SUPPORT"
    else:
        confidence_status = "CONDITIONAL"

    # 2. Check for low confidence / insufficient data fallback
    if confidence_status in ("INSUFFICIENT DATA", "LIMITED"):
        reason_codes.append("LIMITED_SAMPLE_HISTORY")
        return DriverAdvisoryResponse(
            action="HOLD_STRATEGY",
            target_lap=optimal_pit if optimal_pit >= current_lap else None,
            advisory_text="Prediction confidence is limited. Hold strategy and reassess next lap.",
            reason_codes=reason_codes,
            confidence_status=confidence_status,
            model_status=model_status,
            details={
                "current_lap": current_lap,
                "tyre_age": tyre_age,
                "cumulative_debt": round(cumulative_debt, 3),
                "cliff_risk": round(cliff_risk, 3),
            }
        )

    # 3. Assess operational conditions
    is_at_or_past_optimal = (current_lap >= optimal_pit)
    is_near_optimal = (optimal_pit - current_lap <= 2 and current_lap >= earliest_forced_pit)
    is_cliff_imminent = (cliff_risk >= 0.70 or degradation_state == "CRITICAL" or cumulative_debt >= 4.0)
    is_high_debt_rate = (debt_trend >= 0.15 or future_forecast_loss_h5 >= 0.80)
    is_undercut_threat = (competitor_threat in ("HIGH", "CRITICAL"))

    if is_cliff_imminent:
        reason_codes.append("HIGH_CLIFF_RISK")
    if is_high_debt_rate:
        reason_codes.append("RISING_TYRE_DEBT")
    if is_undercut_threat:
        reason_codes.append("COMPETITOR_UNDERCUT_THREAT")
    if is_at_or_past_optimal:
        reason_codes.append("OPTIMAL_WINDOW_REACHED")

    # 4. Generate action & radio advisory message
    if is_at_or_past_optimal or (current_lap >= latest_safe_pit - 1):
        action = "PIT"
        target_lap = current_lap
        if is_cliff_imminent or is_high_debt_rate:
            advisory_text = f"Tyres are degrading quickly. Pit window open, recommend box lap {current_lap}."
        elif is_undercut_threat:
            advisory_text = f"Undercut vulnerability high. Recommend box lap {current_lap} to protect position."
        else:
            advisory_text = f"Optimal tyre life reached. Recommend box lap {current_lap}."
            
    elif is_near_optimal or (is_cliff_imminent and current_lap >= earliest_forced_pit):
        action = "PREPARE_PIT"
        target_lap = optimal_pit
        if is_cliff_imminent:
            advisory_text = f"High degradation risk. Prioritize pit preparation; current optimal window is lap {optimal_pit}–{optimal_pit + 1}."
        elif is_high_debt_rate:
            advisory_text = f"Tyres are degrading quickly. Pit window opens lap {earliest_forced_pit}, recommend box lap {optimal_pit}."
        else:
            advisory_text = f"Tyre performance approaching limit. Prepare for pit window lap {optimal_pit}–{optimal_pit + 1}."
            
    elif is_cliff_imminent and current_lap < earliest_forced_pit:
        action = "HOLD_STRATEGY"
        target_lap = earliest_forced_pit
        advisory_text = f"Elevated tyre debt detected early. Manage pace and target pit window opening lap {earliest_forced_pit}."
        
    else:
        action = "STAY_OUT"
        target_lap = optimal_pit
        reason_codes.append("TYRE_PERFORMANCE_STABLE")
        if debt_trend < 0.05 and cumulative_debt < 1.5:
            advisory_text = "Tyre performance remains stable. Stay out and reassess in two laps."
        else:
            advisory_text = f"Tyres in working window. Stay out; current optimal pit target is lap {optimal_pit}."

    return DriverAdvisoryResponse(
        action=action,
        target_lap=target_lap,
        advisory_text=advisory_text,
        reason_codes=reason_codes,
        confidence_status=confidence_status,
        model_status=model_status,
        details={
            "current_lap": current_lap,
            "tyre_age": tyre_age,
            "cumulative_debt_s": round(cumulative_debt, 3),
            "debt_trend_s_per_lap": round(debt_trend, 3),
            "cliff_risk": round(cliff_risk, 3),
            "earliest_forced_pit": earliest_forced_pit,
            "optimal_pit": optimal_pit,
            "latest_safe_pit": latest_safe_pit,
            "competitor_threat": competitor_threat,
            "sample_count": sample_count,
            "scientific_terminology": {
                "stage1_frozen": "y_hat = 0.1974 + 0.0400 * tyre_age",
                "stage2_frozen": "debt = sum(max(0, residual))",
                "classification": "Estimated Tyre-Performance Debt (Observable Confounder Adjusted)"
            }
        }
    )
