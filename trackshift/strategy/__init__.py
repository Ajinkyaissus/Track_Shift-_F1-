"""
TrackShift — Strategic Warfare Engine Package
=============================================
Exporting all 5 modules, decision fusion, configuration, and simulation engine.
"""

from trackshift.strategy.config import (
    CIRCUIT_METRICS,
    DEFAULT_METRICS,
    COMPOUND_CHARACTERISTICS,
    DEBT_LIQUIDATION_THRESHOLDS,
    UNDERCUT_CONFIG,
    INSTABILITY_WEIGHTS,
    DECISION_WEIGHTS
)

from trackshift.strategy.debt_liquidation import (
    calculate_debt_liquidation,
    stage1_m1_loss
)

from trackshift.strategy.ghost_car_roi import (
    simulate_ghost_car_pit_roi
)

from trackshift.strategy.undercut_vulnerability import (
    evaluate_competitor_undercut
)

from trackshift.strategy.pit_market_spread import (
    compute_pit_market_spread
)

from trackshift.strategy.performance_instability import (
    evaluate_performance_instability
)

from trackshift.strategy.decision_fusion import (
    fuse_strategic_decision
)

from trackshift.strategy.simulator import (
    simulate_full_race_strategies,
    execute_strategic_checkpoint
)

from trackshift.strategy.driver_advisory import (
    generate_driver_advisory,
    DriverAdvisoryResponse
)
from trackshift.strategy.decision_engine import TDSMStrategyEngine

__all__ = [
    "TDSMStrategyEngine",
    "CIRCUIT_METRICS",
    "DEFAULT_METRICS",
    "COMPOUND_CHARACTERISTICS",
    "DEBT_LIQUIDATION_THRESHOLDS",
    "UNDERCUT_CONFIG",
    "INSTABILITY_WEIGHTS",
    "DECISION_WEIGHTS",
    "calculate_debt_liquidation",
    "stage1_m1_loss",
    "simulate_ghost_car_pit_roi",
    "evaluate_competitor_undercut",
    "compute_pit_market_spread",
    "evaluate_performance_instability",
    "fuse_strategic_decision",
    "simulate_full_race_strategies",
    "execute_strategic_checkpoint",
    "generate_driver_advisory",
    "DriverAdvisoryResponse"
]
