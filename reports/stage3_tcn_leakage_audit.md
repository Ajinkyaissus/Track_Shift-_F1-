# Stage 3 TCN Partition & Information Leakage Audit

**Audit Date:** 2026-09-11 17:53:35  
**Model Version:** `v5_tcn_stage3_2026-09-10`  
**Evaluation Protocol:** 60% Train / 20% Val / 20% Frozen Test (Chronological Event Grouping)

## 1. Sequence Causality Verification
- **Endpoint Lap Constraint:** Each sequence ending at lap $N$ contains strictly laps $\le N$.
- **Target Lap:** Strictly lap $N+1$ (future relative to the sequence endpoint).
- **Causality Violations Detected:** **3067** (0 required).

## 2. Stint Boundary Isolation
- **Boundary Rule:** Telemetry sequences are generated strictly per `stint_id`.
- **Cross-Stint Telemetry Concatenation:** None.
- **Cross-Driver / Cross-Session Sequences:** None.
- **Boundary Violations Detected:** **0** (0 required).

## 3. Train / Validation / Test Isolation
- **Event Date Overlap (Train vs Test):** **0** events.
- **Sequence Hash Overlap (Train vs Test):** **0** identical sequence windows.
- **Sliding-Window Cross-Partition Leakage:** None. Test sequences belong strictly to unseen chronological events.

## 4. Normalization Statistics Boundary
- **Scaler Type:** `StandardScaler`
- **Fitting Boundary:** Fitted **STRICTLY on Train Split** ($N=11304$ laps).
- **Test Scaling:** Transformed using serialized train parameters ($\mu, \sigma$) without retraining.
