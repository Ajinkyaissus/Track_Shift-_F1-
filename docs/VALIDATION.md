# TrackShift — Validation Guide

## Test Suite

Run the full test suite with:

    pytest

All 30 test files in tests/ must pass. Two non-test benchmarking scripts have been
removed from tests/ and consolidated into scripts/benchmark.py.

---

## Scientific Invariant Tests

These tests protect the 15 non-negotiable scientific contracts:

    pytest tests/test_final_hardening_pass.py       # tyre-age lineage, M1 constants, Stage 2 debt, TCN boundary
    pytest tests/test_scientific_hardening.py       # degradation curve, debt accumulation, confounder decomposition
    pytest tests/test_constants_single_source.py    # static: single source of truth for all frozen constants
    pytest tests/test_scientific_integrity_audit.py # leakage, feature bounds, M1 invariants
    pytest tests/test_tcn_training_and_leakage.py   # Stage 3 causal TCN, future leakage prevention
    pytest tests/test_temporal_dl.py                # temporal integrity
    pytest tests/test_bootstrap_uncertainty.py      # confidence intervals, saturation detection

---

## System / Production Tests

    pytest tests/test_api_endpoints.py              # FastAPI contract integrity
    pytest tests/test_cache.py tests/test_cache_api.py  # KV cache tier, TTL, stampede protection
    pytest tests/test_precompute.py                 # offline precomputation integrity

---

## Authoritative Validation Scripts

Three authoritative CLI scripts replace all 27 legacy ad-hoc audit runners:

    # All scientific invariants (constants, ablation, debt, TCN, bootstrap, post-race)
    python scripts/validate_scientific.py

    # All production integrity checks (DB schema, startup, cache, API routes, engines)
    python scripts/validate_production.py

    # Latency and throughput benchmarks (p50, p95, p99, concurrent)
    python scripts/benchmark.py

---

## Frontend Verification

    npm --prefix frontend run lint    # Must exit 0, zero warnings
    npm --prefix frontend run build   # Must produce clean minified bundle

---

## Acceptance Gates

A release is blocked unless ALL of the following pass:

1. pytest: 100% of test files pass
2. test_constants_single_source.py: confirms frozen constants are imported from single source
3. scripts/validate_scientific.py: exits 0
4. scripts/validate_production.py: exits 0
5. npm run lint: exits 0 with zero errors/warnings
6. npm run build: exits 0

---

## Manual Smoke Test

1. Start the server: uvicorn api.main:app
2. GET /health -> 200 {"status": "healthy"}
3. GET /api/tyre-intelligence/provenance -> 200, provenance chain present
4. GET /api/tyre-intelligence/degradation-curve?circuit=silverstone&driver=HAM -> 200
5. GET /api/race-intelligence?circuit=silverstone -> 200
6. git status -> no untracked generated reports or benchmark JSONs in working tree
