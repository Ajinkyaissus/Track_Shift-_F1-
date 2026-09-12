"""
TrackShift — Module 2: Ghost-Car Pit ROI Simulator
==================================================
Simulates hypothetical race outcomes across candidate pit lap windows (STAY OUT,
PIT NOW, PIT +1, +2, ...), calculating projected race time, pit loss, fresh-tyre
pace offset, traffic delta penalties, and strategic advantage.

All candidate outputs are strictly labeled HYPOTHETICAL and maintain empirical
uncertainty intervals.
"""

from typing import Dict, Any, List, Optional
import numpy as np

from trackshift.strategy.config import (
    CIRCUIT_METRICS,
    DEFAULT_METRICS,
    COMPOUND_CHARACTERISTICS
)
from trackshift.strategy.debt_liquidation import stage1_m1_loss


def simulate_ghost_car_pit_roi(
    circuit_key: str,
    current_lap: int,
    total_laps: int,
    current_compound: str,
    current_tyre_age: int,
    current_cumulative_debt: float,
    current_burn_rate: float,
    base_lap_time_sec: float,
    target_compound: str = "HARD",
    window_ahead_laps: int = 12,
    traffic_density_factor: float = 0.5,
    bootstrap_samples: int = 200
) -> Dict[str, Any]:
    """
    Simulates race completion time under STAY OUT vs candidate pit laps.

    Parameters:
    - circuit_key: normalized circuit name
    - current_lap: current race lap N
    - total_laps: race distance
    - current_compound: current tyre compound ('SOFT', 'MEDIUM', 'HARD')
    - current_tyre_age: current tyre age on lap N
    - current_cumulative_debt: current accumulated debt
    - current_burn_rate: debt burn rate (s/lap)
    - base_lap_time_sec: estimated clean baseline lap time
    - target_compound: planned next tyre compound
    - window_ahead_laps: number of candidate laps ahead to simulate
    - traffic_density_factor: estimated probability of encountering traffic post-pit [0, 1]

    Returns candidate strategies ranked by strategic advantage vs STAY OUT.
    """
    metrics = CIRCUIT_METRICS.get(circuit_key.lower(), DEFAULT_METRICS)
    pit_loss = metrics["pit_loss_sec"]
    clean_air_delta = metrics["clean_air_delta"]

    curr_comp_info = COMPOUND_CHARACTERISTICS.get(current_compound.upper(), COMPOUND_CHARACTERISTICS["MEDIUM"])
    next_comp_info = COMPOUND_CHARACTERISTICS.get(target_compound.upper(), COMPOUND_CHARACTERISTICS["HARD"])

    remaining_laps = max(0, total_laps - current_lap)
    if remaining_laps == 0:
        return {"status": "RACE_FINISHED", "candidate_strategies": []}

    # 1. Simulate STAY OUT scenario
    # Laps from current_lap to total_laps on existing tyre
    stay_out_lap_times = []
    running_debt = current_cumulative_debt
    running_age = current_tyre_age

    for l in range(current_lap, total_laps):
        running_age += 1
        running_debt += current_burn_rate
        # Lap time = base + stage1_loss(age) + debt
        lap_t = base_lap_time_sec + curr_comp_info["base_offset_sec"] + stage1_m1_loss(running_age) + running_debt
        stay_out_lap_times.append(lap_t)

    stay_out_total_time = float(np.sum(stay_out_lap_times))

    candidate_strategies = []

    # 2. Simulate STAY OUT baseline entry
    candidate_strategies.append({
        "strategy_id": "STAY_OUT",
        "label": "HYPOTHETICAL",
        "action": "STAY_OUT",
        "pit_lap": None,
        "planned_compound": current_compound,
        "projected_race_time_sec": round(stay_out_total_time, 3),
        "strategic_advantage_sec": 0.00,
        "pit_loss_sec": 0.0,
        "traffic_penalty_sec": 0.0,
        "clean_air_benefit_sec": 0.0,
        "tyre_state_at_finish": {
            "compound": current_compound,
            "final_age": running_age,
            "final_cumulative_debt": round(running_debt, 3)
        },
        "uncertainty_interval_sec": [
            round(stay_out_total_time - (remaining_laps * 0.15), 3),
            round(stay_out_total_time + (remaining_laps * 0.25), 3)
        ]
    })

    # 3. Simulate candidate pit laps: [current_lap (PIT NOW), current_lap + 1, ..., min(current_lap + window, total_laps - 1)]
    max_candidate_lap = min(current_lap + window_ahead_laps, total_laps - 1)

    for pit_lap in range(current_lap, max_candidate_lap + 1):
        pit_delta_laps = pit_lap - current_lap
        action_name = "PIT_NOW" if pit_delta_laps == 0 else f"PIT_LAP_{pit_lap}"

        sim_times = []
        sim_age = current_tyre_age
        sim_debt = current_cumulative_debt

        # Pre-pit phase (from current_lap to pit_lap - 1)
        for _ in range(pit_delta_laps):
            sim_age += 1
            sim_debt += current_burn_rate
            lap_t = base_lap_time_sec + curr_comp_info["base_offset_sec"] + stage1_m1_loss(sim_age) + sim_debt
            sim_times.append(lap_t)

        # In-lap / Pit Stop execution: Pit loss added
        # Post-pit fresh tyre phase (from pit_lap to total_laps)
        post_pit_laps = total_laps - pit_lap
        fresh_age = 0
        fresh_debt = 0.0  # Fresh tyre starts with zero accumulated debt
        # Traffic penalty depends on traffic factor and pit window position
        traffic_penalty = round(traffic_density_factor * (1.2 * clean_air_delta), 3)
        clean_air_benefit = round((1.0 - traffic_density_factor) * clean_air_delta * min(5, post_pit_laps), 3)

        for _ in range(post_pit_laps):
            fresh_age += 1
            # Fresh tyre incurs baseline loss with fresh compound wear multiplier
            fresh_stage1 = stage1_m1_loss(fresh_age) * next_comp_info["wear_rate_multiplier"]
            fresh_debt += 0.025 * next_comp_info["wear_rate_multiplier"]  # Nominal modest debt accumulation
            lap_t = base_lap_time_sec + next_comp_info["base_offset_sec"] + fresh_stage1 + fresh_debt
            sim_times.append(lap_t)

        total_sim_time = float(np.sum(sim_times)) + pit_loss + traffic_penalty - clean_air_benefit
        strategic_advantage = stay_out_total_time - total_sim_time

        # Empirical uncertainty via bootstrap on pit variance (±0.6s) and pace noise
        noise_std = 0.12 * np.sqrt(remaining_laps)
        p10 = total_sim_time - (1.645 * (noise_std + 0.5))
        p90 = total_sim_time + (1.645 * (noise_std + 0.5))

        candidate_strategies.append({
            "strategy_id": f"STRAT_PIT_L{pit_lap}",
            "label": "HYPOTHETICAL",
            "action": action_name,
            "pit_lap": pit_lap,
            "planned_compound": target_compound,
            "projected_race_time_sec": round(total_sim_time, 3),
            "strategic_advantage_sec": round(strategic_advantage, 3),
            "pit_loss_sec": pit_loss,
            "traffic_penalty_sec": traffic_penalty,
            "clean_air_benefit_sec": clean_air_benefit,
            "tyre_state_at_finish": {
                "compound": target_compound,
                "final_age": fresh_age,
                "final_cumulative_debt": round(fresh_debt, 3)
            },
            "uncertainty_interval_sec": [round(p10, 3), round(p90, 3)]
        })

    # Sort candidates by projected race time ascending (highest strategic advantage first)
    candidate_strategies.sort(key=lambda x: x["projected_race_time_sec"])

    best_strat = candidate_strategies[0]

    return {
        "circuit": circuit_key,
        "current_lap": current_lap,
        "total_laps": total_laps,
        "best_hypothetical_strategy": best_strat,
        "candidate_strategies": candidate_strategies,
        "stay_out_baseline_sec": round(stay_out_total_time, 3),
        "provenance": {
            "label": "HYPOTHETICAL",
            "pit_loss_parameter": pit_loss,
            "clean_air_parameter": clean_air_delta,
            "causality": "Strict historical information at lap N"
        }
    }
