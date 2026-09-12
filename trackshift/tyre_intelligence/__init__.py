"""
TrackShift Confounder-Aware Tyre Performance Intelligence
=========================================================
Isolates observable confounding variables (fuel weight proxy, track evolution,
traffic context) from practice and race telemetry to generate clean estimated
tyre performance degradation curves with post-race validation.

Frozen Architectural Foundations:
- Stage 1 M1 Baseline: y_hat = 0.1974 + 0.0400 * tyre_age
- Stage 2 Estimated Debt: sum(max(0, residual))
- Stage 3 TCN Behavioral Intelligence
- Stage 4 Sensitivity Engine
- Strategic Warfare Engine
"""

from trackshift.tyre_intelligence.provenance import (
    FEATURE_PROVENANCE_CATALOG,
    FeatureProvenance,
    get_provenance_catalog_dict,
)
from trackshift.tyre_intelligence.confounders import (
    ConfounderContext,
    ObservableConfounderEstimator,
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)
from trackshift.tyre_intelligence.model import (
    ContextualResidualLedger,
    DecompositionPoint,
    ObservableDecompositionModel,
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
)
from trackshift.tyre_intelligence.degradation_curve import (
    DegradationPoint,
    EstimatedDegradationCurve,
    TyreDegradationCurveGenerator,
)
from trackshift.tyre_intelligence.post_race_validation import (
    HorizonEvaluation,
    PostRaceValidationReport,
    PostRaceValidator,
)
from trackshift.tyre_intelligence.ablation import (
    AblationStudyReport,
    ConfounderAblationSuite,
    ModelAblationResult,
)

__all__ = [
    "FEATURE_PROVENANCE_CATALOG",
    "FeatureProvenance",
    "get_provenance_catalog_dict",
    "ConfounderContext",
    "ObservableConfounderEstimator",
    "FUEL_EFFECT_COEFFICIENT",
    "TRACK_EVOLUTION_COEFFICIENT",
    "TRAFFIC_EFFECT_COEFFICIENT",
    "ContextualResidualLedger",
    "DecompositionPoint",
    "ObservableDecompositionModel",
    "STAGE1_M1_INTERCEPT",
    "STAGE1_M1_SLOPE",
    "DegradationPoint",
    "EstimatedDegradationCurve",
    "TyreDegradationCurveGenerator",
    "HorizonEvaluation",
    "PostRaceValidationReport",
    "PostRaceValidator",
    "AblationStudyReport",
    "ConfounderAblationSuite",
    "ModelAblationResult",
]
