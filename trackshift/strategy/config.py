"""
TrackShift — Strategic Warfare Engine Config & Constants
=======================================================
All thresholds, weights, and circuit parameters are explicitly defined here.
No hidden or arbitrary constants.
"""

from typing import Dict, Any

# Circuit-specific typical race laps and pit delta loss (seconds)
CIRCUIT_METRICS: Dict[str, Dict[str, float]] = {
    "monza": {"total_laps": 53, "pit_loss_sec": 24.2, "length_km": 5.793, "clean_air_delta": 0.8},
    "spa": {"total_laps": 44, "pit_loss_sec": 21.8, "length_km": 7.004, "clean_air_delta": 0.7},
    "silverstone": {"total_laps": 52, "pit_loss_sec": 24.5, "length_km": 5.891, "clean_air_delta": 0.9},
    "monaco": {"total_laps": 78, "pit_loss_sec": 19.5, "length_km": 3.337, "clean_air_delta": 1.4},
    "hungaroring": {"total_laps": 70, "pit_loss_sec": 21.2, "length_km": 4.381, "clean_air_delta": 1.1},
    "bahrain": {"total_laps": 57, "pit_loss_sec": 23.4, "length_km": 5.412, "clean_air_delta": 0.6},
    "jeddah": {"total_laps": 50, "pit_loss_sec": 20.8, "length_km": 6.174, "clean_air_delta": 0.6},
    "abu_dhabi": {"total_laps": 58, "pit_loss_sec": 22.6, "length_km": 5.281, "clean_air_delta": 0.7},
    "cota": {"total_laps": 56, "pit_loss_sec": 22.0, "length_km": 5.513, "clean_air_delta": 0.8},
    "miami": {"total_laps": 57, "pit_loss_sec": 20.5, "length_km": 5.412, "clean_air_delta": 0.7},
    "las_vegas": {"total_laps": 50, "pit_loss_sec": 21.0, "length_km": 6.201, "clean_air_delta": 0.5},
    "interlagos": {"total_laps": 71, "pit_loss_sec": 21.5, "length_km": 4.309, "clean_air_delta": 0.9},
    "suzuka": {"total_laps": 53, "pit_loss_sec": 22.8, "length_km": 5.807, "clean_air_delta": 0.9},
    "singapore": {"total_laps": 62, "pit_loss_sec": 28.5, "length_km": 4.940, "clean_air_delta": 1.3},
    "albert_park": {"total_laps": 58, "pit_loss_sec": 20.2, "length_km": 5.278, "clean_air_delta": 0.8},
    "baku": {"total_laps": 51, "pit_loss_sec": 21.1, "length_km": 6.003, "clean_air_delta": 0.6},
    "catalunya": {"total_laps": 66, "pit_loss_sec": 22.4, "length_km": 4.657, "clean_air_delta": 1.0},
    "montreal": {"total_laps": 70, "pit_loss_sec": 18.5, "length_km": 4.361, "clean_air_delta": 0.7},
    "red_bull_ring": {"total_laps": 71, "pit_loss_sec": 20.0, "length_km": 4.318, "clean_air_delta": 0.8},
    "zandvoort": {"total_laps": 72, "pit_loss_sec": 20.4, "length_km": 4.259, "clean_air_delta": 1.1},
    "losail": {"total_laps": 57, "pit_loss_sec": 24.0, "length_km": 5.419, "clean_air_delta": 0.7},
    "rodriguez": {"total_laps": 71, "pit_loss_sec": 22.2, "length_km": 4.304, "clean_air_delta": 0.8},
    "shanghai": {"total_laps": 56, "pit_loss_sec": 23.1, "length_km": 5.451, "clean_air_delta": 0.8},
    "imola": {"total_laps": 63, "pit_loss_sec": 26.8, "length_km": 4.909, "clean_air_delta": 1.2}
}

DEFAULT_METRICS = {"total_laps": 55, "pit_loss_sec": 22.0, "length_km": 5.0, "clean_air_delta": 0.8}

# Compound expected baseline life and fresh-tyre pace offsets relative to MEDIUM
COMPOUND_CHARACTERISTICS: Dict[str, Dict[str, Any]] = {
    "SOFT": {"base_offset_sec": -0.65, "typical_life_laps": 18, "wear_rate_multiplier": 1.45},
    "MEDIUM": {"base_offset_sec": 0.00, "typical_life_laps": 28, "wear_rate_multiplier": 1.00},
    "HARD": {"base_offset_sec": 0.55, "typical_life_laps": 38, "wear_rate_multiplier": 0.70},
    "INTERMEDIATE": {"base_offset_sec": 3.50, "typical_life_laps": 25, "wear_rate_multiplier": 1.10},
    "WET": {"base_offset_sec": 7.00, "typical_life_laps": 30, "wear_rate_multiplier": 0.90}
}

# Module 1: Debt Liquidation Thresholds
DEBT_LIQUIDATION_THRESHOLDS = {
    "debt_low": 1.0,        # seconds
    "debt_moderate": 2.5,   # seconds
    "debt_high": 4.5,       # seconds
    "burn_low": 0.10,       # sec/lap
    "burn_moderate": 0.25,  # sec/lap
    "burn_high": 0.45       # sec/lap
}

# Module 3: Undercut Vulnerability Weights & Bounds
UNDERCUT_CONFIG = {
    "pit_window_sec": 26.0,          # Relevant gap window around pit delta
    "fresh_tyre_outlap_gain": 1.40,  # Expected 1-lap outlap advantage on fresh tyre
    "gap_weight": 0.35,
    "burn_weight": 0.25,
    "age_weight": 0.20,
    "drift_weight": 0.10,
    "traffic_weight": 0.10,
    "threshold_moderate": 30.0,
    "threshold_high": 60.0,
    "threshold_critical": 80.0
}

# Module 5: Performance Instability Weights
INSTABILITY_WEIGHTS = {
    "pace_variance_scale": 1.0,    # 1.0s variance corresponds to full scale
    "pace_variance_weight": 0.30,
    "burn_rate_scale": 0.40,       # 0.40s/lap burn rate
    "burn_rate_weight": 0.25,
    "age_fraction_weight": 0.20,
    "anomaly_score_weight": 0.15,
    "drift_score_weight": 0.10,
    "threshold_moderate": 0.35,
    "threshold_high": 0.60,
    "threshold_critical": 0.80
}

# Strategic Decision Fusion Score Weights
DECISION_WEIGHTS = {
    "race_time_advantage_weight": 1.20,   # Score points per second saved
    "position_gain_weight": 2.50,         # Score points per expected position gained
    "win_prob_gain_weight": 15.0,         # Score points per +100% win prob
    "podium_prob_gain_weight": 8.0,       # Score points per +100% podium prob
    "tyre_debt_cost_weight": 0.60,        # Penalty points per second debt
    "cliff_risk_penalty_weight": 3.00,    # Penalty points for high cliff risk
    "competitor_threat_penalty_weight": 2.50, # Penalty for opponent undercut vulnerability
    "uncertainty_discount_weight": 0.50   # Penalty for wide variance intervals
}
