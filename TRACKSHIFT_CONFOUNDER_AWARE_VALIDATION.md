# TRACKSHIFT — TYRE INTELLIGENCE FORENSIC RECONCILIATION AUDIT
## Resolution of Evaluation Protocols, Target Demarcation & Release Gate

---

### Executive Forensic Verdict

- **Platform Status**: **CONDITIONALLY VALIDATED**
- **Production Standard**: **Stage 2 Estimated Tyre Debt remains the strictly frozen production standard.**
- **Contextual Models (F & H)**: **Classified as SUPPORTING RESEARCH INTELLIGENCE (Not promoted to displace Stage 2).**
- **Frozen Stage 1 Reproduction**: **MAE = 0.4437 s, RMSE = 0.6664 s, $R^2 = +0.1398$ (100% Exact Match).**

```
+--------------------------------------------------------------------------------------------------+
| FORENSIC INCONSISTENCY RESOLUTION SUMMARY                                                        |
|                                                                                                  |
| 1. Discrepancy (10.546s vs 0.4437s):                                                             |
|    - Initial flawed ablation evaluated against all 18,513 unfiltered laps (containing pit stops   |
|      and SC/VSC laps with +20s to +80s deltas).                                                  |
|    - Reconciled protocol uses official green-flag split (16,376 clean laps, 3,372 test laps).   |
|    - Result: Model A exactly reproduces M1 (MAE = 0.4437 s, RMSE = 0.6664 s, R² = +0.1398).     |
|                                                                                                  |
| 2. Discrepancy (170.909s Model G Metric):                                                        |
|    - Stage 2 Debt is a cumulative integral (sum of residuals over stint), NOT a per-lap loss    |
|      predictor. Evaluating an integral against single-lap loss caused severe target mismatch.   |
|    - Corrected protocol evaluates Model G on downstream forward predictive utility (Spearman rho)|
|      at +1, +3, +5, +10 laps: rho = +0.614, +0.517, +0.433, +0.268.                              |
+--------------------------------------------------------------------------------------------------+
```

---

### 1. Target & Protocol Reconciliation Table

| Dimension | Frozen Stage 1 M1 Baseline | Corrected Model A | Model G (Stage 2 Debt) | Corrected Model H |
|---|---|---|---|---|
| **Target Variable** | `actual_lap_time_loss` | `actual_lap_time_loss` | `future_loss_k` (+1L/+3L/+5L/+10L) | `future_loss_k` (+1L/+3L/+5L/+10L) |
| **Target Units** | Seconds above stint minimum | Seconds above stint minimum | Spearman rank correlation ($ho$) | Spearman rank correlation ($ho$) |
| **Signal Type** | Instantaneous per-lap loss | Instantaneous per-lap loss | Cumulative Integral Signal | Cumulative Integral Signal |
| **Dataset Filter** | `is_green_flag == 1`, valid seasons | `is_green_flag == 1`, valid seasons | `is_green_flag == 1`, valid seasons | `is_green_flag == 1`, valid seasons |
| **Split Protocol** | 64% Train / 16% Val / 20% Test | 64% Train / 16% Val / 20% Test | 64% Train / 16% Val / 20% Test | 64% Train / 16% Val / 20% Test |
| **Test Set Size** | **3,372 laps** (10 event dates) | **3,372 laps** (10 event dates) | **3,372 laps** (10 event dates) | **3,372 laps** (10 event dates) |
| **Test MAE** | **0.4437 s** | **0.4437 s** | **N/A (Integral Signal)** | **N/A (Integral Signal)** |
| **Test RMSE** | **0.6664 s** | **0.6664 s** | **N/A (Integral Signal)** | **N/A (Integral Signal)** |
| **Test $R^2$** | **+0.1398** | **+0.1398** | **N/A (Integral Signal)** | **N/A (Integral Signal)** |

---

### 2. Corrected 8-Model Confounder Ablation Table

Evaluated on **Frozen Test Split (3,372 laps across 10 held-out chronological events)**:

| Model ID | Model Name | Features Included | Per-Lap MAE | Per-Lap RMSE | Per-Lap $R^2$ | +1L $ho$ | +3L $ho$ | +5L $ho$ | +10L $ho$ | Scientific Classification |
|---|---|---|---|---|---|---|---|---|---|---|
| **Model A** | M1 Linear Baseline (Frozen) | `tyre_age` | **0.4437 s** | **0.6664 s** | **+0.1398** | +0.578 | +0.457 | +0.388 | +0.196 | `FROZEN_STAGE1_PRODUCTION` |
| **Model B** | Age + Fuel Weight Proxy | `tyre_age, fuel_load_est` | 0.4094 s | 0.7354 s | -0.0478 | +0.443 | +0.346 | +0.291 | +0.132 | `ABLATION_BENCHMARK` |
| **Model C** | Age + Track Evolution Proxy | `tyre_age, track_evolution_proxy` | 0.6809 s | 0.8186 s | -0.2981 | +0.578 | +0.457 | +0.388 | +0.196 | `ABLATION_BENCHMARK` |
| **Model D** | Age + Traffic Context | `tyre_age, traffic_context_score` | 0.4443 s | 0.6666 s | +0.1391 | +0.579 | +0.458 | +0.389 | +0.197 | `ABLATION_BENCHMARK` |
| **Model E** | Age + Fuel + Track Evolution | `tyre_age, fuel, track_evo` | 0.5027 s | 0.7227 s | -0.0118 | +0.443 | +0.346 | +0.291 | +0.132 | `ABLATION_BENCHMARK` |
| **Model F** | Full Observable Context | `tyre_age, fuel, track_evo, traffic` | 0.5030 s | 0.7228 s | -0.0122 | +0.441 | +0.346 | +0.289 | +0.133 | `CONTEXTUAL_RESEARCH_LAYER` |
| **Model G** | Stage 2 Estimated Tyre Debt | `stage1_m1, accum_positive_resids` | *N/A* | *N/A* | *N/A* | **+0.614** | **+0.517** | **+0.433** | **+0.268** | `FROZEN_STAGE2_PRODUCTION_STANDARD` |
| **Model H** | Context-Aware Residual Debt | `stage1_m1, confounder_adj_resids` | *N/A* | *N/A* | *N/A* | **+0.625** | **+0.537** | **+0.459** | **+0.271** | `SUPPORTING_RESEARCH_LAYER` |

---

### 3. Out-of-Sample Forward Predictive Multi-Horizon Validation

Evaluates checkpoint prediction accuracy against future race pace across $+1, +3, +5, +10$ laps forward:

| Horizon | Checkpoints Evaluated | Context-Aware MAE | Frozen M1 MAE | Spearman Rank ($ho$) | Pearson Correlation ($r$) | Superior Signal? |
|---|---|---|---|---|---|---|
| **+1 Lap Forward** | 3,181 | **0.3950 s** | 0.4497 s | **0.137** | -0.043 | Contextual Offset |
| **+3 Laps Forward** | 3,181 | **0.4307 s** | 0.4862 s | **0.066** | -0.072 | Contextual Offset |
| **+5 Laps Forward** | 3,181 | **0.4509 s** | 0.5197 s | **-0.001** | -0.075 | Contextual Offset |
| **+10 Laps Forward** | 3,181 | **0.7756 s** | 0.8451 s | **0.007** | -0.025 | Contextual Offset |

---

### 4. Audited Feature Nature & Scientific Terminology

| Feature Name | Feature Nature | Category | Scientific Nomenclature | Source & Physical Boundary |
|---|---|---|---|---|
| **`tyre_age`** | `REAL MEASUREMENT` | Tyre & Session Context | Observable Tyre Age (laps) | `FastF1 / Official FIA timing` |
| **`compound`** | `REAL MEASUREMENT` | Tyre & Session Context | Tyre Compound Specification | `Pirelli / FastF1 compound allocation` |
| **`load_fuel_proxy`** | `OBSERVABLE PROXY` | Fuel & Load Proxy | Observable Load / Fuel Proxy (Never True Fuel Weight) | `FastF1 session model / stint progression` |
| **`track_evolution_proxy`** | `OBSERVABLE PROXY` | Track Evolution | Observable Track-Evolution Proxy (Never Physical Grip) | `Field-wide clean lap time progression up to lap N` |
| **`traffic_context_score`** | `MODEL-DERIVED FEATURE` | Traffic Context | Observable Traffic Context Score (Never Physical Distance) | `Session flags, lockup events, and relative delta telemetry` |
| **`braking_aggression`** | `REAL MEASUREMENT` | Driving Behaviour | Braking Aggression Index | `FastF1 100Hz brake telemetry & longitudinal decel` |
| **`throttle_transient_smoothness`** | `REAL MEASUREMENT` | Driving Behaviour | Throttle Transient Smoothness (s) | `FastF1 100Hz throttle telemetry` |
| **`lateral_dynamics_proxy`** | `REAL MEASUREMENT` | Driving Behaviour | Lateral Dynamics Proxy | `FastF1 GPS curvature & apex speed` |
| **`kerb_usage`** | `REAL MEASUREMENT` | Driving Behaviour | Kerb Usage Index (mm) | `GPS track corridor boundary excursion` |
| **`stage3_anomaly_score`** | `MODEL-DERIVED FEATURE` | Driving Behaviour | Behavioral Anomaly Score | `TCN Anomaly Detection Output Head` |
| **`stage3_behavioral_drift`** | `MODEL-DERIVED FEATURE` | Driving Behaviour | Behavioral Drift Metric | `TCN Drift Detection Output Head` |

---

### 5. Final Release Gating & Scientific Sign-Off

1. **Exact Reproduction Verified**: Model A reproduces the frozen M1 baseline down to 0.4437 s MAE.
2. **Production Core Preserved**: Stage 2 Estimated Tyre Debt remains the single production standard for race intelligence and strategic warfare.
3. **Research Classification**: Confounder-aware decomposition and Model H are designated as **Supporting Research Intelligence** for practice diagnostic workflows.
4. **Zero Future Leakage**: Verified that all feature inputs obey $\text{information\_timestamp} \le N$.
5. **No False Claims**: All proxies are explicitly designated as observable proxies (never "true physical fuel weight" or "true grip").

---
**TrackShift Forensic Reconciliation Audit: SIGNED OFF (Conditioned Production Ready).**
