"""
Unit tests for TrackShift Strategic Warfare Engine.
"""

import pytest
from trackshift.strategy import (
    calculate_debt_liquidation,
    stage1_m1_loss,
    simulate_ghost_car_pit_roi,
    evaluate_competitor_undercut,
    compute_pit_market_spread,
    evaluate_performance_instability,
    fuse_strategic_decision,
)


def test_stage1_m1_loss():
    """Verify frozen Stage 1 M1 Baseline."""
    assert round(stage1_m1_loss(0), 4) == 0.1974
    assert round(stage1_m1_loss(10), 4) == 0.5974
    assert round(stage1_m1_loss(20), 4) == 0.9974


def test_debt_liquidation():
    """Verify Module 1 debt liquidation and burn rate."""
    debts = [0.1, 0.2, 0.3, 0.4]
    res = calculate_debt_liquidation(debts, current_tyre_age=10)
    assert res["current_debt_sec"] == 1.0
    assert res["debt_burn_rate_sec_per_lap"] == 0.3
    assert "+1_laps" in res["horizon_projections"]
    assert res["liquidation_state"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def test_ghost_car_pit_roi():
    """Verify Module 2 hypothetical pit simulations."""
    res = simulate_ghost_car_pit_roi(
        circuit_key="monza",
        current_lap=20,
        total_laps=53,
        current_compound="MEDIUM",
        current_tyre_age=20,
        current_cumulative_debt=1.5,
        current_burn_rate=0.15,
        base_lap_time_sec=83.5
    )
    assert res["circuit"] == "monza"
    assert "best_hypothetical_strategy" in res
    assert len(res["candidate_strategies"]) > 0
    assert all(c["label"] == "HYPOTHETICAL" for c in res["candidate_strategies"])


def test_undercut_vulnerability():
    """Verify Module 3 competitor undercut radar."""
    competitors = [
        {"driver_code": "NOR", "gap_to_our_car_sec": 1.5, "tyre_age": 18, "compound": "MEDIUM", "cumulative_debt": 1.5, "debt_burn_rate": 0.15, "recent_pace_slope": 0.05, "drift_score": 0.04},
        {"driver_code": "HAM", "gap_to_our_car_sec": 12.0, "tyre_age": 8, "compound": "HARD", "cumulative_debt": 0.2, "debt_burn_rate": 0.02, "recent_pace_slope": 0.01, "drift_score": 0.01}
    ]
    res = evaluate_competitor_undercut(
        circuit_key="monza",
        our_driver="ALB",
        our_gap_to_leader=3.0,
        our_tyre_age=18,
        our_compound="MEDIUM",
        our_debt=1.2,
        our_burn_rate=0.12,
        competitors=competitors,
        current_lap=18
    )
    assert len(res["competitor_evaluations"]) == 2
    assert res["highest_threat_competitor"]["driver_code"] == "NOR"


def test_pit_market_spread():
    """Verify Module 4 pit market spread and tactical flexibility."""
    res = compute_pit_market_spread(
        current_lap=20,
        total_laps=53,
        optimal_pit_lap=24,
        current_tyre_age=20,
        max_recommended_age=28,
        cliff_risk_score=0.4,
        highest_undercut_threat_score=50.0,
        strategic_advantage_array=[]
    )
    assert res["earliest_forced_pit"] <= res["optimal_pit"]
    assert res["optimal_pit"] <= res["latest_safe_pit"]
    assert res["strategic_spread_laps"] >= 0


def test_performance_instability():
    """Verify Module 5 performance instability scoring and naming."""
    res = evaluate_performance_instability(
        recent_lap_times=[83.5, 83.6, 83.7],
        debt_burn_rate=0.08,
        current_tyre_age=15,
        compound="MEDIUM",
        stage3_anomaly_score=0.05,
        stage3_drift_score=0.04,
        current_lap=15
    )
    assert res["warning_label"] == "performance-instability warning"
    assert res["cliff_risk"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert len(res["deterioration_window"]) == 2


def test_decision_fusion():
    """Verify Strategic Decision Fusion MCDA."""
    m1 = calculate_debt_liquidation([0.1, 0.15], current_tyre_age=15)
    m2 = simulate_ghost_car_pit_roi("monza", 20, 53, "MEDIUM", 20, 1.5, 0.15, 83.5)
    m3 = evaluate_competitor_undercut("monza", "ALB", 4.0, 20, "MEDIUM", 1.5, 0.15, [], 20)
    m4 = compute_pit_market_spread(20, 53, 24, 20, 28, 0.3, 40.0, [])
    m5 = evaluate_performance_instability([83.5, 83.6, 83.7], 0.1, 20, "MEDIUM", 0.05, 0.04, 20)

    res = fuse_strategic_decision("ALB", 20, 53, m1, m2, m3, m4, m5, current_position=3)
    rec = res["recommended_decision"]
    assert rec["action"] in ["PIT", "STAY_OUT", "ATTACK", "DEFEND"]
    assert "decision_score" in rec
    assert len(res["battle_matrix"]) >= 1
