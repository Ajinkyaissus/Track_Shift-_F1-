"""
TrackShift — Module 4: Pit Stop Market Spread & Tactical Window Analyzer
======================================================================
Computes:
- earliest_forced_pit: Earliest lap where tyre debt burn exceeds tolerable threshold
  or competitor undercut window forces reactive stop.
- optimal_pit: Lap that mathematically minimizes expected total race time.
- latest_safe_pit: Latest lap before cumulative debt and delta to fresh-tyre cars
  triggers irreversible track position loss.
- strategic_spread: Difference (latest_safe_pit - earliest_forced_pit) measuring tactical flexibility.
"""

from typing import Dict, Any, List, Optional
import numpy as np


def compute_pit_market_spread(
    current_lap: int,
    total_laps: int,
    optimal_pit_lap: int,
    current_tyre_age: int,
    max_recommended_age: int,
    cliff_risk_score: float,
    highest_undercut_threat_score: float,
    strategic_advantage_array: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculates the strategic pit spread and tactical windows.

    Parameters:
    - current_lap: Current race lap N
    - total_laps: Race distance
    - optimal_pit_lap: Lap minimizing total race time from ghost-car simulator
    - current_tyre_age: Age of tyre on lap N
    - max_recommended_age: Typical lifespan for compound (e.g. 28 for Medium)
    - cliff_risk_score: Current performance instability / cliff risk [0, 1]
    - highest_undercut_threat_score: Highest opponent vulnerability / threat score [0, 100]
    - strategic_advantage_array: Array of candidate pit lap evaluations
    """
    remaining_laps = max(0, total_laps - current_lap)
    if remaining_laps <= 3:
        return {
            "status": "END_OF_RACE",
            "earliest_forced_pit": current_lap,
            "optimal_pit": current_lap,
            "latest_safe_pit": current_lap,
            "strategic_spread_laps": 0,
            "tactical_flexibility": "LOCKED"
        }

    # 1. Earliest forced pit lap calculation:
    # If cliff risk is high (>0.6) or opponent threat is critical (>80), forced pit is immediate.
    # Otherwise, earliest forced pit is constrained by tyre minimum viable stint length.
    if cliff_risk_score >= 0.75 or highest_undercut_threat_score >= 80.0:
        earliest_forced_pit = current_lap
    elif cliff_risk_score >= 0.50 or highest_undercut_threat_score >= 60.0:
        earliest_forced_pit = min(current_lap + 1, optimal_pit_lap)
    else:
        earliest_forced_pit = max(current_lap, optimal_pit_lap - 4)

    # 2. Optimal pit lap (bounded by race boundaries)
    optimal_pit = int(np.clip(optimal_pit_lap, earliest_forced_pit, total_laps - 2))

    # 3. Latest safe pit lap calculation:
    # Based on compound max life minus current age, and where strategic advantage stays within 1.5s of peak.
    tyre_life_remaining = max(1, max_recommended_age - current_tyre_age)
    potential_latest = current_lap + tyre_life_remaining

    # Find last candidate lap where strategic advantage does not drop by > 2.0s from optimal
    if strategic_advantage_array:
        best_adv = max(x.get("strategic_advantage_sec", 0.0) for x in strategic_advantage_array)
        safe_candidates = [
            x.get("pit_lap") for x in strategic_advantage_array
            if x.get("pit_lap") is not None and (best_adv - x.get("strategic_advantage_sec", 0.0)) <= 2.5
        ]
        if safe_candidates:
            latest_safe_pit = max(safe_candidates)
        else:
            latest_safe_pit = min(potential_latest, optimal_pit + 3)
    else:
        latest_safe_pit = min(potential_latest, optimal_pit + 3)

    latest_safe_pit = int(np.clip(latest_safe_pit, optimal_pit, total_laps - 2))

    # 4. Strategic Spread
    strategic_spread = max(0, latest_safe_pit - earliest_forced_pit)

    # Flexibility classification
    if strategic_spread >= 6:
        flexibility = "HIGH_FLEXIBILITY"
        flex_desc = "Broad tactical window allows reactive positioning against safety cars or competitor moves."
    elif strategic_spread >= 3:
        flexibility = "MODERATE_FLEXIBILITY"
        flex_desc = "Standard 3-5 lap pit execution corridor."
    elif strategic_spread >= 1:
        flexibility = "TIGHT_WINDOW"
        flex_desc = "Narrow 1-2 lap window; delayed stop incurs compounding performance penalty."
    else:
        flexibility = "FORCED_TRIGGER"
        flex_desc = "Immediate pit trigger required due to cliff risk or aggressive opponent undercut."

    return {
        "current_lap": current_lap,
        "total_laps": total_laps,
        "earliest_forced_pit": earliest_forced_pit,
        "optimal_pit": optimal_pit,
        "latest_safe_pit": latest_safe_pit,
        "strategic_spread_laps": strategic_spread,
        "tactical_flexibility": flexibility,
        "flexibility_description": flex_desc,
        "windows": {
            "optimal_window": [max(current_lap, optimal_pit - 1), min(total_laps - 2, optimal_pit + 1)],
            "forced_window": [earliest_forced_pit, optimal_pit],
            "overcut_opportunity_window": [optimal_pit + 1, latest_safe_pit] if latest_safe_pit > optimal_pit else []
        },
        "definitions": {
            "earliest_forced_pit": "First lap where staying out risks net loss to undercut or rapid degradation",
            "optimal_pit": "Lap minimizing total estimated race completion time",
            "latest_safe_pit": "Final lap before performance debt causes severe track position loss",
            "strategic_spread": "latest_safe_pit - earliest_forced_pit (operational margin)"
        }
    }
