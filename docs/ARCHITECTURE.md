# TrackShift — Hybrid ML/DL + KV Cache Architecture

TrackShift 2026 · Technical Architecture Specification

```text
                                TRACKSHIFT
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
          OFFLINE PIPELINE                        ONLINE API
                  │                                   │
                  ▼                                   ▼
        Classical ML Baseline                      FastAPI
        (HistGradientBoosting)                        │
                  │                                   ▼
                  ▼                                KV CACHE
         Tyre Debt Ledger                    (Redis / Memory LRU)
       (Deterministic Parquet)                        │
                  │                          ┌────────┴────────┐
                  ▼                          │                 │
             Temporal DL                    HIT               MISS
          (TCN Dilated Conv)                 │                 │
                  │                          │         Single-Flight Compute
                  ▼                          │                 │
         Behavioral Embedding                │            Store Cache
            (z ∈ R^16)                       │                 │
                  │                          └────────┬────────┘
                  ▼                                   │
         Classical ML Attribution                     ▼
             (Ridge / EBM)                         React UI
                  │                              (JavaScript)
                  ▼
       Physical Saturation Bounds
       (R_max * tanh(R_lin/R_max))
                  │
                  ▼
          Offline Precompute
       (python -m api.jobs.precompute)
                  │
                  ▼
          Redis / Memory KV
```

---

## 1. Architectural Principles

> **"Deep Learning understands complex temporal driving behavior. Classical ML provides fast, structured and interpretable attribution. A deterministic Tyre Debt ledger maintains auditability. Physics-based constraints keep counterfactuals realistic. Precomputation and KV caching move expensive computation off the critical user-facing path."**

### Separation of Concerns:
1. **Offline Computation**:
   - Environmental baseline modeling (`HistGradientBoostingRegressor`).
   - Residual tyre debt computation stored in `data/residual_ledger.parquet` (943 evaluated laps).
   - PyTorch Temporal Convolutional Network (`TemporalBehavioralTCN`) extracting 16-D behavioral embeddings $z_{\text{behavior}} \in \mathbb{R}^{16}$.
   - Classical ML attribution fitting interpretable per-driver / per-track behavioral coefficients.
   - Comprehensive offline prewarm job (`python -m api.jobs.precompute`) caching all 13 circuit maps, ledgers, attributions, embeddings, and counterfactuals.
2. **Online Serving**:
   - Cache-first FastAPI serving layer.
   - Distributed Redis KV cache with automatic, transparent in-memory LRU fallback when Redis is absent.
   - Single-flight async stampede protection (coalesces burst requests for identical missing keys into a single computation).
   - Strict physical saturation guardrail: $R_{\text{bounded}} = R_{\text{max}} \cdot \tanh(R_{\text{linear}} / R_{\text{max}})$.
   - Sub-5ms warm-cache responses across all analytical endpoints.

---

## 2. Model Pipeline Layers

### Stage 1 — Environmental Baseline
- **Model**: `HistGradientBoostingRegressor` (Model Version: `v3_stage1_2026-09-07`).
- **Inputs**: Compound, track ID, tyre age, tyre age squared, estimated fuel load, track evolution index.
- **Output**: Clean reference lap time loss baseline.
- **Provenance**: Logged in SQLite `model_registry` with held-out RMSE.

### Stage 2 — Deterministic Tyre Debt Ledger
- **Formula**:
  $$\text{Residual}_i = \text{Actual Lap Time Loss}_i - \text{Predicted Baseline Loss}_i$$
  $$\text{Tyre Debt}_n = \sum_{i=1}^n \max(0, \text{Residual}_i - \text{Expected Degradation})$$
- **Persistence**: `data/residual_ledger.parquet` (auditable, deterministic, no black-box neural networks in the debt ledger).

### Stage 3 — Temporal Deep Learning Behavioral Embedding
- **Architecture**: Dilated Causal 1D Temporal Convolutional Network (`TemporalBehavioralTCN`) with residual connections, LayerNorm, and GELU.
- **Input Channels**: Sequential telemetry (Braking aggression, Throttle transient smoothness, Lateral dynamics proxy, Kerb usage, Lockup flag rate).
- **Embedding**: Compact behavioral latent representation $z_{\text{behavior}} \in \mathbb{R}^{16}$.
- **Determinism**: Fully deterministic for identical `(model_version, stint_id, telemetry_version)`.
- **Alternative**: LSTM architecture (`TemporalBehavioralLSTM`) supported under the unified `BehavioralModelWrapper` interface.

### Stage 4 — Interpretable Attribution & Physical Saturation
- **Attribution**: Maps $z_{\text{behavior}}$ and explicit behavioral features to lap debt attribution percentages using regularized Ridge regression.
- **Physical Saturation Guardrail**:
  $$R_{\text{bounded}} = R_{\text{max}} \cdot \tanh\left(\frac{R_{\text{linear}}}{R_{\text{max}}}\right)$$
  Where $R_{\text{max}} = \min(0.35 \times \text{stint\_length}, 7.5\text{ laps})$.

---

## 3. KV Cache Architecture

### Tiered Cache Strategy:
```text
Request ──> [Redis Client Pool] ──(Connected?)──► Redis KV Store (Port 6379)
                   │
                   └──(Unavailable / Offline)──► In-Memory LRU Store (Thread-Safe Async)
```

### Versioned Cache Key Specification:
- Circuit Geometry: `circuit:{circuit_id}:map:{data_version}:{map_version}`
- Circuit Detail: `circuit:{circuit_id}:detail:{data_version}`
- Circuit Sessions: `circuit:{circuit_id}:sessions:{data_version}`
- Circuit Stints: `circuit:{circuit_id}:stints:{driver}:{compound}:{data_version}`
- Stint Ledger: `stint:{stint_id}:ledger:{ledger_version}`
- Stint Attribution: `stint:{stint_id}:attribution:{model_version}`
- Counterfactual: `stint:{stint_id}:counterfactual:{model_version}:{feature}:{delta_pct}`
- Behavioral Embedding: `embedding:{model_version}:{stint_id}:{telemetry_version}`
- Stint Comparison: `stints:compare:{model_version}:{stint_a}:{stint_b}`

### Cache Stampede Protection:
Uses `single_flight(key, compute_fn)`:
- If 50 simultaneous concurrent requests arrive for an uncached key, an async lock ensures exactly 1 DL/ML inference is executed.
- The remaining 49 concurrent tasks wait on the in-flight lock and receive the cached result upon resolution.

---

## 4. API Endpoints & Observability

| Endpoint | Method | Cache Key Pattern | SLA Target | Empirical Warm Latency |
|---|---|---|---|---|
| `/circuits/{id}/map` | GET | `circuit:{id}:map:...` | < 100 ms | ~12.38 ms (large JSON payload) |
| `/stints/{id}/ledger` | GET | `stint:{id}:ledger:...` | < 50 ms | 0.76 ms |
| `/stints/{id}/attribution` | GET | `stint:{id}:attribution:...` | < 50 ms | 0.66 ms |
| `/stints/{id}/counterfactual` | POST | `stint:{id}:counterfactual:...` | < 50 ms | 0.66 ms |
| `/stints/{id}/signature_transfer`| POST | `stint:{id}:signature_transfer:...`| < 50 ms | 0.70 ms |
| `/stints/compare` | GET | `stints:compare:...` | < 50 ms | 0.75 ms |
| `/metrics` | GET | Direct stats | < 5 ms | 0.15 ms |
| `/admin/cache/invalidate/stint/{id}`| POST | Invalidation | < 10 ms | 0.50 ms |

---

## 5. Offline Precomputation

Offline prewarming command:
```bash
python -m api.jobs.precompute
```

Precomputed Assets:
- **13/13 Circuits** geometry and SVG rotation maps.
- **69 Stints** from 2024 season sessions.
- **943 Evaluated Laps** in residual tyre debt ledger.
- **69 DL Behavioral Embeddings** ($z \in \mathbb{R}^{16}$).
- **69 Attribution Decompositions**.
- **1,380 Precomputed Counterfactual Projections** across standard parameter grids.
