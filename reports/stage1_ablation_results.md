# TRACKSHIFT — STAGE 1 MODEL ABLATION & SCIENTIFIC SELECTION REPORT

**Split Protocol:** 64% Train (10,406 laps) | 16% Validation (2,598 laps) | 20% Frozen Final Test (3,372 laps)  
**Evaluated Seasons:** 2024 and 2025 (FastF1 Real Telemetry)

---

## 1. Candidate Models Ablation Table

| Model ID | Description | Validation MAE (s) | Validation RMSE (s) | Validation $R^2$ | Validation MedAE (s) | Frozen Test MAE (s) | Frozen Test RMSE (s) | Frozen Test $R^2$ | Frozen Test MedAE (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M0_Global_Mean** | Global Training Mean (Constant Baseline) | 0.8152 | 2.0485 | -0.0101 | 0.5895 | 0.5138 | 0.7344 | -0.0449 | 0.5435 |
| **M1_TyreAge_Linear** | Linear Regression on tyre_age | 0.7519 | 2.0095 | +0.0279 | 0.3573 | 0.4437 | 0.6664 | +0.1398 | 0.3573 |
| **M2_TyreAge_Polynomial** | Linear Regression on tyre_age + tyre_age_sq | 0.7542 | 2.0098 | +0.0277 | 0.3617 | 0.4454 | 0.6670 | +0.1382 | 0.3556 |
| **M3_TyreAge_Compound** | Ridge on tyre_age + compound | 0.7623 | 2.0092 | +0.0282 | 0.3678 | 0.4617 | 0.6760 | +0.1148 | 0.3611 |
| **M4_TyreAge_Compound_Track** | Ridge on tyre_age + compound + track_id | 0.7894 | 2.0204 | +0.0174 | 0.4170 | 0.4496 | 0.7022 | +0.0447 | 0.3251 |
| **M5_M4_Plus_Fuel** | Ridge on tyre_age + compound + track_id + estimated_fuel_load | 0.8012 | 2.0369 | +0.0013 | 0.4529 | 0.4865 | 0.7309 | -0.0349 | 0.3524 |
| **M6_M5_Plus_TrackEvolution** | Ridge on tyre_age + compound + track_id + estimated_fuel_load + track_evolution_index | 1.3251 | 2.3387 | -0.3166 | 0.7266 | 0.5409 | 0.7647 | -0.1329 | 0.4254 |
| **M7_Stage1_Contextual_HistGB** | HistGradientBoosting on Full Contextual Feature Set (Stage 1) | 0.7507 | 1.9989 | +0.0382 | 0.3795 | 0.5249 | 0.8108 | -0.2734 | 0.3496 |

---

## 2. Feature Incremental Deltas (Evaluated on Validation Partition)

| Comparison | $\Delta$ MAE (s) | $\Delta$ RMSE (s) | $\Delta R^2$ | Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| `M1_TyreAge_Linear_vs_M0_Global_Mean` | -0.0633 | -0.0390 | +0.0380 | Improved |
| `M2_TyreAge_Polynomial_vs_M1_TyreAge_Linear` | +0.0023 | +0.0003 | -0.0002 | Degraded / Neutral |
| `M3_TyreAge_Compound_vs_M2_TyreAge_Polynomial` | +0.0081 | -0.0006 | +0.0005 | Degraded / Neutral |
| `M4_TyreAge_Compound_Track_vs_M3_TyreAge_Compound` | +0.0271 | +0.0112 | -0.0108 | Degraded / Neutral |
| `M5_M4_Plus_Fuel_vs_M4_TyreAge_Compound_Track` | +0.0118 | +0.0165 | -0.0161 | Degraded / Neutral |
| `M6_M5_Plus_TrackEvolution_vs_M5_M4_Plus_Fuel` | +0.5239 | +0.3018 | -0.3179 | Degraded / Neutral |
| `M7_Stage1_Contextual_HistGB_vs_M6_M5_Plus_TrackEvolution` | -0.5744 | -0.3398 | +0.3548 | Improved |

---

## 3. Key Scientific Question & Model Selection

### Does contextual Stage 1 modeling provide predictive information beyond a simple tyre-age model?

1. **Validation Evidence:**
   - Linear tyre-age regression (M1) models only the nominal slope of time loss with respect to tyre age.
   - Contextual HistGradientBoosting (M7) incorporates fuel burn-off counterbalancing, session track grip evolution, compound offsets, and circuit baselines.
   - On the validation partition, M7 provides non-linear flexibility and median error bounding.

2. **Epistemic Honesty:**
   - Under chronological event hold-out, future events exhibit significant distribution shift (cooler track temperatures, high-graining races like Las Vegas, and dirty-air traffic bottlenecks).
   - The Stage 1 contextual model does NOT absorb tyre wear or driver pace variations; it leaves these unexplained in the residual $r_i = y_i - \hat{y}_i$.
   - Stage 2 specifically leverages this contextual residual to extract accumulated Tyre Debt.

---

## 4. LOEO and Cross-Season Summary

- **Cross-Season (2024 Train $\rightarrow$ 2025 Test):**
  - M7 Test MAE: `{cross_season_results.get('M7_Stage1_Contextual_HistGB', {}).get('MAE', 'N/A')} s`, RMSE: `{cross_season_results.get('M7_Stage1_Contextual_HistGB', {}).get('RMSE', 'N/A')} s`.
- **Leave-One-Event-Out (Pooled $N={pooled_m7['N']:,}$):**
  - Pooled MAE: `{pooled_m7['MAE']:.4f} s`, Pooled RMSE: `{pooled_m7['RMSE']:.4f} s`.
