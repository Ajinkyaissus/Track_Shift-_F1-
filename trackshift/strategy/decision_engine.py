"""
trackshift/strategy/decision_engine.py — Deterministic Decision Support on top of TDSM Forecasts.

Non-learned, transparent strategy engine translating multi-horizon tyre degradation forecasts
into actionable race decisions (PIT, STAY_OUT, PUSH, MANAGE, ATTACK, DEFEND, MONITOR).
Strictly contains NO hard-coded pit laps.
"""

from typing import Dict, Any, List, Optional


class TDSMStrategyEngine:
    """
    Deterministic Strategy Decision Engine.
    
    Principles:
    1. Zero hard-coded lap numbers (e.g. no 'pit on lap 25').
    2. Decisions driven strictly by TDSM multi-horizon forecasts (+1, +3, +5, +10),
       observed delta rates, and race delta economics.
    3. Fully explainable with structured reason codes.
    """
    def __init__(
        self,
        default_pit_loss_sec: float = 22.0,
        cliff_deg_threshold_sec: float = 2.4,
        acceleration_threshold: float = 0.25,
        model_version: str = "TDSM-v1.0-2024-FROZEN"
    ):
        self.default_pit_loss = default_pit_loss_sec
        self.cliff_deg_threshold = cliff_deg_threshold_sec
        self.accel_threshold = acceleration_threshold
        self.model_version = model_version

    def evaluate_strategy(
        self,
        current_lap: int,
        tyre_life: int,
        compound: str,
        current_d: float,
        delta_d: float,
        delta2_d: float,
        tdsm_forecast: Dict[str, float],
        total_laps: int = 57,
        gap_to_ahead_sec: Optional[float] = None,
        gap_to_behind_sec: Optional[float] = None,
        pit_loss_sec: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates dynamic strategy recommendation without hard-coded pit laps.
        """
        pit_loss = pit_loss_sec or self.default_pit_loss
        remaining_laps = max(0, total_laps - current_lap)
        f1 = tdsm_forecast.get("+1", current_d)
        f3 = tdsm_forecast.get("+3", current_d)
        f5 = tdsm_forecast.get("+5", current_d)
        f10 = tdsm_forecast.get("+10", current_d)

        reason_codes = []
        supporting_preds = {
            "D_current": round(float(current_d), 3),
            "Delta_D": round(float(delta_d), 3),
            "Forecast_+1": round(float(f1), 3),
            "Forecast_+3": round(float(f3), 3),
            "Forecast_+5": round(float(f5), 3),
            "Forecast_+10": round(float(f10), 3)
        }

        # 1. Degradation Rate and Cliff Risk Analysis
        # Forecasted pace loss slope over next 5 laps
        deg_slope_5 = (f5 - current_d) / 5.0 if f5 is not None else 0.1
        deg_slope_10 = (f10 - current_d) / 10.0 if f10 is not None else 0.1

        is_cliff_imminent = (f3 > self.cliff_deg_threshold) or (f5 > self.cliff_deg_threshold + 0.5)
        is_accelerating = (delta2_d > self.accel_threshold) or (deg_slope_5 > 0.35)

        # 2. Pit Recovery Economics
        # Compare remaining race time staying out vs pitting for fresh tyres
        # Fresh tyre pace advantage is estimated at ~current_d + 0.3s
        # Time lost over remaining laps if staying out:
        # projected avg degradation staying out ~ (current_d + f5)/2 * remaining_laps
        # Time lost pitting: pit_loss + fresh_tyre_loss
        projected_loss_stay_out = ((current_d + f5) / 2.0) * min(remaining_laps, 15)
        projected_loss_if_pit = pit_loss + (0.2 * min(remaining_laps, 15))

        # 3. Decision Logic (Dynamic)
        if remaining_laps <= 3:
            # End of race: pitting almost never recovers pit loss in <= 3 laps
            action = "STAY_OUT"
            target_lap = total_laps
            reason_codes.append("END_OF_RACE_STAY_OUT")
            confidence = 0.95

        elif is_cliff_imminent and remaining_laps > 8:
            action = "PIT"
            target_lap = current_lap + 1
            reason_codes.append("TYRE_CLIFF_FORECAST_EXCEEDED")
            if is_accelerating:
                reason_codes.append("DEGRADATION_ACCELERATION_HIGH")
            confidence = 0.90

        elif (projected_loss_stay_out > projected_loss_if_pit) and remaining_laps >= 12:
            action = "PIT"
            target_lap = current_lap + (2 if not is_accelerating else 1)
            reason_codes.append("PIT_TIME_RECOVERY_FAVORABLE")
            confidence = 0.85

        elif gap_to_behind_sec is not None and 1.2 <= gap_to_behind_sec <= 2.8 and (f3 - current_d > 0.4):
            # Competitor within undercut zone while our forecast shows degradation rising
            action = "DEFEND"
            target_lap = current_lap + 1
            reason_codes.append("UNDERCUT_VULNERABILITY_DEFEND")
            confidence = 0.80

        elif gap_to_ahead_sec is not None and 0.8 <= gap_to_ahead_sec <= 2.0 and deg_slope_5 < 0.15:
            action = "ATTACK"
            target_lap = current_lap + 3
            reason_codes.append("PACE_ADVANTAGE_ATTACK_WINDOW")
            confidence = 0.80

        elif is_accelerating or (f5 > 1.8):
            action = "MANAGE"
            target_lap = current_lap + 4
            reason_codes.append("THERMAL_MANAGEMENT_RECOMMENDED")
            confidence = 0.75

        elif deg_slope_5 < 0.08 and current_d < 1.0:
            action = "PUSH"
            target_lap = current_lap + 6
            reason_codes.append("LOW_DEGRADATION_PUSH_WINDOW")
            confidence = 0.85

        else:
            action = "MONITOR"
            target_lap = current_lap + 5
            reason_codes.append("STABLE_TYRE_STATE_MONITOR")
            confidence = 0.70

        return {
            "action": action,
            "target_lap": target_lap,
            "reason_codes": reason_codes,
            "supporting_predictions": supporting_preds,
            "confidence": confidence,
            "model_version": self.model_version
        }
