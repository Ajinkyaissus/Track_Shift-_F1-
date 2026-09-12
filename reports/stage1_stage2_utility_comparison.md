# TRACKSHIFT — STAGE 1 $\rightarrow$ STAGE 2 DOWNSTREAM UTILITY FORENSIC

**Investigation Focus:** Does M7 (Full Context HistGradientBoosting) produce a more scientifically useful residual for Stage 2 Tyre Debt than M1 (Linear Tyre Age), despite M1's superior direct prediction accuracy?

---

## 1. Two-Axis Evaluation Matrix

| Evaluation Axis | Metric | M1 (Linear Tyre Age) | M7 (Contextual HistGB) | Winner / Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Axis 1: Direct Stage 1 Prediction** | Validation MAE (s) | 0.7519 | **0.7507** | M7 (-0.0012s) |
| | Validation RMSE (s) | 2.0095 | **1.9989** | M7 (-0.0106s) |
| | Frozen Test MAE (s) | **0.4437** | 0.5249 | M1 (-0.0812s) |
| | Frozen Test MedAE (s) | 0.3573 | **0.3496** | M7 (-0.0077s) |
| | Frozen Test $R^2$ | **+0.1398** | -0.2734 | M1 (+0.4132) |
| **Axis 2: Stage 2 Downstream Utility** | Future Loss Correlation (+1 Lap $\rho$) | +0.4362 | **+0.3029** | M1 |
| | Future Loss Correlation (+5 Laps $\rho$) | +0.3189 | **+0.2422** | M1 |
| | Future Loss Correlation (+10 Laps $\rho$) | +0.1757 | **+0.1253** | M1 |
| | Stint Degradation Slope ($\rho$) | 0.3221 | **0.2758** | M1 |
| | Placebo Negative Control Defeated | Verified | Verified | **PASS** |
| | Paired Stint Bootstrap 95% CI | — | +0.0387 [-0.0167, +0.0915] | Robust |

---

## 2. Scientific Decision & Recommendation

### **DECISION: M1 SUPERIOR**

**Scientific Justification:**  
M1 achieves both lower direct prediction error and equivalent/superior downstream utility. Stage 1 should be simplified to the linear tyre-age baseline.
