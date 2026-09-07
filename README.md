# TrackShift — Multi-Circuit F1 Telemetry & Tyre Debt Intelligence

> **Hybrid ML + Deep Learning Inference Architecture with a Cache-First Serving Layer**  
> *Real-Time Telemetry Streaming, Causal Attribution & Physically Bounded Counterfactual Coaching*

---

## 1. System Architecture

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

## 2. Decoupled Service-Oriented Directory Structure

```text
TrackShift/
├── api/                             # FastAPI Backend & Serving Layer
│   ├── cache/                       # Tiered KV Caching Service
│   │   ├── __init__.py              # Exports CacheService, MemoryCache, CacheKeys
│   │   ├── cache_keys.py            # Versioned cache key definitions
│   │   ├── cache_service.py         # Unified Redis/Memory cache + single-flight lock
│   │   └── redis_client.py          # Async Redis connection pool wrapper
│   ├── jobs/                        # Offline Precomputation & Background Jobs
│   │   ├── __init__.py
│   │   └── precompute.py            # Offline prewarming pipeline across 13 circuits
│   ├── models/                      # ML & Deep Learning Model Registry
│   │   ├── __init__.py
│   │   ├── behavioral_model.py      # PyTorch TCN, LSTM, and physical saturation guardrail
│   │   └── registry.py              # In-memory model registry & provenance loader
│   ├── routers/                     # Dedicated Route Controllers
│   │   ├── __init__.py
│   │   ├── admin.py                 # Cache invalidation & metrics endpoints
│   │   ├── circuits.py              # 13 circuit geometry, maps, & session endpoints
│   │   ├── signatures.py            # Driver profiles & signature transfer endpoints
│   │   └── stints.py                # Stints, ledgers, attributions, & counterfactual endpoints
│   ├── services/                    # Decoupled Domain Services
│   │   ├── __init__.py
│   │   ├── circuits_service.py      # Circuit metadata & geometry processing
│   │   ├── counterfactual_service.py# Physically bounded counterfactual math engine
│   │   ├── signatures_service.py    # Driver behavioral transfer calculation
│   │   ├── stints_service.py        # Stints query & comparison service
│   │   └── tyre_debt_service.py     # Deterministic ledger & attribution service
│   ├── main.py                      # FastAPI entrypoint, lifespan injection, & WebSocket
│   ├── schema.sql                   # SQLite schema (tracks, stints, models, coefficients)
│   └── tyredebt.db                  # Persisted SQLite database
│
├── pipeline/                        # Data Ingestion & Feature Engineering
│   ├── build_real_dataset.py        # Multi-circuit dataset assembler
│   ├── circuit_geometry.py          # GPS coordinates & corner apex generator
│   ├── features.py                  # High-frequency telemetry feature extraction
│   ├── ingest.py                    # FastF1 session loader
│   ├── model_stage1.py              # Stage 1 Environmental Baseline training
│   ├── model_stage2.py              # Stage 2 Residual Tyre Debt ledger builder
│   ├── model_stage3.py              # Stage 3/4 Temporal DL & Attribution modeling
│   ├── multicircuit_ingest.py       # Multi-circuit batch ingestion
│   └── validate_multicircuit.py     # Cross-track dataset validation
│
├── data/                            # Persisted Data Layer (Parquet + Raw Telemetry)
│   ├── 2024/                        # Raw FastF1 telemetry archives
│   ├── baseline_predictions.parquet # Stage 1 predicted lap losses
│   ├── circuit_geometry.parquet     # 13 circuit GPS tracks & corner points
│   ├── laps.parquet                 # 1,021 raw extracted telemetry laps
│   └── residual_ledger.parquet      # 943 evaluated green-flag laps with cumulative debt
│
├── frontend/                        # React Frontend (Pure JavaScript / JSX)
│   ├── public/                      # Static assets & offline JSON fallbacks
│   ├── src/
│   │   ├── components/              # Reusable UI widgets (CircuitMap, CircuitSelector)
│   │   ├── screens/                 # Dashboard views (StintDetail, DriverCompare)
│   │   ├── api.js                   # API client with automatic offline fallback
│   │   ├── App.jsx                  # Root application router
│   │   └── index.css                # Formula 1 visual design tokens
│   └── package.json                 # Vite + React configuration
│
├── tests/                           # Complete Automated Test Suite (41/41 Passing)
│   ├── test_api_endpoints.py        # Core API endpoint contracts
│   ├── test_cache.py                # Cache hit/miss/expiration/stampede tests
│   ├── test_cache_api.py            # API cache serving & invalidation tests
│   ├── test_circuits.py             # 13 circuit geometry & session tests
│   ├── test_counterfactual_correctness.py # Causal correctness tests
│   ├── test_model_registry.py       # Model provenance & dataset integrity
│   ├── test_pipeline_features.py    # Telemetry feature extraction tests
│   ├── test_precompute.py           # Offline precompute validation
│   └── test_temporal_dl.py          # TCN shapes, embeddings, & saturation tests
│
├── benchmark.py                     # Empirical latency & throughput benchmark suite
├── generate_report_pdf.py           # PDF report generator (ReportLab)
├── simulate_live.py                 # Real-time race telemetry simulator
├── TrackShift_RealTime_Latency_Simulation_Report.pdf # Executive engineering report
├── requirements.txt                 # Python runtime dependencies
└── README.md                        # Master repository documentation
```

---

## 3. Quickstart & Commands

```bash
# 1. Install Dependencies
pip install -r requirements.txt
npm --prefix frontend install

# 2. Run Precompute Job (Prewarms KV Cache)
python -m api.jobs.precompute

# 3. Start Backend Server
uvicorn api.main:app --reload --port 8000

# 4. Start Frontend UI
npm --prefix frontend run dev

# 5. Run Real-Time Telemetry Simulation
python simulate_live.py 2024_monza_R_VER_1

# 6. Run Test Suite (41/41 Tests)
python -m pytest tests -v

# 7. Run Benchmarking Suite
python benchmark.py
```
