"""
TrackShift — Module 5: Performance Instability & Cliff Warning Engine
===================================================================
Evaluates recent rolling pace variance, lap-time slope, debt burn rate, tyre age
fraction, Stage 3 behavioral drift, and Stage 3 anomaly score.

Produces:
- instability_score: Normalized metric [0, 1.0] of lap-performance deterioration risk.
- cliff_risk: Categorical warning state ('LOW', 'MODERATE', 'HIGH', 'CRITICAL').
- potential_deterioration_window: Estimated lap range where performance drop is likely.

Strictly non-causal nomenclature:
- 'performance-instability warning'
- 'cliff-risk warning'
Never implies physical mechanical tyre failure.
"""

from typing import Dict, Any, List
import numpy as np

from trackshift.strategy.config import INSTABILITY_WEIGHTS, COMPOUND_CHARACTERISTICS


def evaluate_performance_instability(
    recent_lap_times: List[float],
    debt_burn_rate: float,
    current_tyre_age: int,
    compound: str,
    stage3_anomaly_score: float = 0.0,
    stage3_drift_score: float = 0.0,
    current_lap: int = 1
) -> Dict[str, Any]:
    """
    Computes performance instability and cliff risk score.

    Parameters:
    - recent_lap_times: Sequence of last 3-5 clean lap times in seconds.
    - debt_burn_rate: Rate of debt accumulation (s/lap).
    - current_tyre_age: Current tyre age in laps.
    - compound: Tyre compound ('SOFT', 'MEDIUM', 'HARD').
    - stage3_anomaly_score: TCN validated anomaly head score [0, 1].
    - stage3_drift_score: TCN validated behavioral drift head score [0, 1].
    - current_lap: Current race lap.
    """
    cfg = INSTABILITY_WEIGHTS
    comp_info = COMPOUND_CHARACTERISTICS.get(compound.upper(), COMPOUND_CHARACTERISTICS["MEDIUM"])
    typical_life = comp_info["typical_life_laps"]

    # 1. Rolling Pace Variance & Slope
    if len(recent_lap_times) >= 3:
        pace_var = float(np.var(recent_lap_times))
        # Linear slope over recent laps (s/lap)
        x = np.arange(len(recent_lap_times))
        y = np.array(recent_lap_times)
        if len(recent_lap_times) > 1 and np.std(x) > 0:
            slope = float(np.polyfit(x, y, 1)[0])
        else:
            slope = 0.0
    elif len(recent_lap_times) == 2:
        pace_var = float((recent_lap_times[1] - recent_lap_times[0]) ** 2 / 2.0)
        slope = float(recent_lap_times[1] - recent_lap_times[0])
    else:
        pace_var = 0.0
        slope = 0.0

    # 2. Tyre age fraction relative to typical compound life
    age_fraction = float(np.clip(current_tyre_age / max(1, typical_life), 0.0, 2.0))

    # 3. Normalized components for instability score
    var_component = float(np.clip(pace_var / cfg["pace_variance_scale"], 0.0, 1.5))
    burn_component = float(np.clip(max(0.0, debt_burn_rate) / cfg["burn_rate_scale"], 0.0, 1.5))
    anomaly_component = float(np.clip(stage3_anomaly_score, 0.0, 1.0))
    drift_component = float(np.clip(stage3_drift_score, 0.0, 1.0))

    # 4. Composite Instability Score [0, 1.0]
    raw_score = (
        (cfg["pace_variance_weight"] * var_component) +
        (cfg["burn_rate_weight"] * burn_component) +
        (cfg["age_fraction_weight"] * min(1.0, age_fraction)) +
        (cfg["anomaly_score_weight"] * anomaly_component) +
        (cfg["drift_score_weight"] * drift_component)
    )

    instability_score = float(np.clip(raw_score, 0.0, 1.0))

    # 5. Cliff Risk Classification
    if instability_score >= cfg["threshold_critical"] or (age_fraction > 1.3 and slope > 0.4):
        cliff_risk = "CRITICAL"
        risk_desc = "High pace variance and rapid debt accumulation indicate immediate performance cliff entry."
    elif instability_score >= cfg["threshold_high"] or age_fraction > 1.1:
        cliff_risk = "HIGH"
        risk_desc = "Elevated performance degradation rate; sharp lap-time loss expected within 1-2 laps."
    elif instability_score >= cfg["threshold_moderate"] or age_fraction > 0.85:
        cliff_risk = "MODERATE"
        risk_desc = "Standard progressive tyre-performance degradation within manageable operating window."
    else:
        cliff_risk = "LOW"
        risk_desc = "Stable tyre-performance regime with low unexplained variance."

    # 6. Potential Deterioration Window Estimation
    # Estimated laps until severe pace drop (>1.2s/lap degradation)
    if cliff_risk == "CRITICAL":
        det_window = [current_lap, current_lap + 1]
    elif cliff_risk == "HIGH":
        det_window = [current_lap + 1, current_lap + 3]
    elif cliff_risk == "MODERATE":
        remaining_to_cliff = max(2, int(typical_life - current_tyre_age))
        det_window = [current_lap + remaining_to_cliff, current_lap + remaining_to_cliff + 4]
    else:
        remaining_to_cliff = max(5, int(typical_life - current_tyre_age))
        det_window = [current_lap + remaining_to_cliff, current_lap + remaining_to_cliff + 6]

    return {
        "current_lap": current_lap,
        "compound": compound,
        "current_tyre_age": current_tyre_age,
        "instability_score": round(instability_score, 3),
        "cliff_risk": cliff_risk,
        "warning_label": "performance-instability warning",
        "description": risk_desc,
        "deterioration_window": det_window,
        "metric_components": {
            "rolling_pace_variance_sec2": round(pace_var, 4),
            "recent_pace_slope_sec_per_lap": round(slope, 4),
            "debt_burn_rate_sec_per_lap": round(debt_burn_rate, 4),
            "age_fraction_of_nominal": round(age_fraction, 3),
            "stage3_anomaly_score": round(stage3_anomaly_score, 3),
            "stage3_drift_score": round(stage3_drift_score, 3)
        },
        "provenance": {
            "nomenclature": "observational performance instability",
            "physical_wear_implied": False
        }
    }
