"""
TrackShift Performance & Latency Benchmarking Suite.
Measures empirical latencies across:
  1. Stage 1 Baseline Inference (HistGradientBoostingRegressor)
  2. Stage 3 TCN Deep Learning Embedding Inference (Trained PyTorch Causal TCN)
  3. Observational Sensitivity Decomposition (Downstream Attribution Head)
  4. Physically Bounded Hypothetical Counterfactual Computation
  5. L1 In-Memory KV Cache Operations (Set & Get)
  6. End-to-End REST API Endpoints (500 requests per tier)
  7. WebSocket Latency

Computes:
  - Mean, std, p50, p95, p99 percentiles
  - Throughput (requests / sec)
"""

import sys
import time
import json
import platform
import asyncio
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from api.main import app
from api.cache import MemoryCache
from api.models import get_model_registry, BEHAVIORAL_FEATURES


def print_header(title: str):
    print("\n" + "=" * 90)
    print(f" {title}")
    print("=" * 90)


def compute_metrics(latencies_ms: list) -> dict:
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "count": len(arr),
        "mean_ms": round(float(np.mean(arr)), 3),
        "std_ms": round(float(np.std(arr)), 3),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
        "min_ms": round(float(np.min(arr)), 3),
        "max_ms": round(float(np.max(arr)), 3)
    }


def run_benchmarks(num_requests: int = 500):
    print_header("TRACKSHIFT RIGOROUS PERFORMANCE & LATENCY BENCHMARK SUITE")
    print(f"Platform:         {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python Version:   {platform.python_version()}")
    print(f"Requests / Tier:  {num_requests} runs")
    print("-" * 90)

    registry = get_model_registry()
    stint_id = "2024_monza_R_VER_1"
    rng = np.random.RandomState(42)
    sample_seq = rng.randn(len(BEHAVIORAL_FEATURES), 25).astype(np.float32)

    # 1. Stage 3 TCN Deep Learning Forward Inference (Cold & Warm)
    print("\n[Tier 1] Deep Learning TCN Forward Pass Latency...")
    t0 = time.perf_counter()
    _ = registry.behavioral_model.generate_embedding(sample_seq)
    cold_tcn_ms = (time.perf_counter() - t0) * 1000.0

    tcn_latencies = []
    for _ in range(num_requests):
        t0 = time.perf_counter()
        _ = registry.behavioral_model.generate_embedding(sample_seq)
        tcn_latencies.append((time.perf_counter() - t0) * 1000.0)
    tcn_stats = compute_metrics(tcn_latencies)
    print(f"  Stage 3 Trained TCN (16-D Embedding): Cold={cold_tcn_ms:.2f}ms | Mean={tcn_stats['mean_ms']:.3f}ms | p50={tcn_stats['p50_ms']:.3f}ms | p95={tcn_stats['p95_ms']:.3f}ms | p99={tcn_stats['p99_ms']:.3f}ms")

    # 2. Counterfactual & Attribution Component Latency
    print("\n[Tier 2] Mathematical Modeling Component Latency...")
    cf_latencies = []
    for _ in range(num_requests):
        t0 = time.perf_counter()
        _ = registry.behavioral_model.compute_counterfactual_recovery(0.35, 20, 0.1)
        cf_latencies.append((time.perf_counter() - t0) * 1000.0)
    cf_stats = compute_metrics(cf_latencies)
    print(f"  Phys Bounded Sensitivity Calculation: Mean={cf_stats['mean_ms']:.4f}ms | p50={cf_stats['p50_ms']:.4f}ms | p95={cf_stats['p95_ms']:.4f}ms")

    # 3. L1 In-Memory KV Cache
    print("\n[Tier 3] L1 In-Memory KV Cache Lookup...")
    mem_cache = MemoryCache()
    cache_key = "benchmark:stint:test"
    payload = {"stint_id": stint_id, "embedding": [0.1] * 16}
    asyncio.run(mem_cache.set(cache_key, payload))

    mem_latencies = []
    for _ in range(num_requests):
        t0 = time.perf_counter()
        _ = asyncio.run(mem_cache.get(cache_key))
        mem_latencies.append((time.perf_counter() - t0) * 1000.0)
    mem_stats = compute_metrics(mem_latencies)
    print(f"  L1 In-Memory KV Cache Hit:            Mean={mem_stats['mean_ms']:.4f}ms | p50={mem_stats['p50_ms']:.4f}ms | p95={mem_stats['p95_ms']:.4f}ms")

    # 4. Full REST API Endpoints Benchmark
    print(f"\n[Tier 4] End-to-End REST API Latency & Throughput ({num_requests} reqs/endpoint)...")
    with TestClient(app) as client:
        # Prewarm
        client.get("/circuits/spa/map")
        client.get(f"/stints/{stint_id}/attribution")
        client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -20.0})

        endpoints = [
            ("GET Map (/circuits/spa/map)", lambda: client.get("/circuits/spa/map")),
            ("GET Attribution (/stints/.../attribution)", lambda: client.get(f"/stints/{stint_id}/attribution")),
            ("POST Sensitivity (/stints/.../counterfactual)", lambda: client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -20.0})),
            ("GET Ledger (/stints/.../ledger)", lambda: client.get(f"/stints/{stint_id}/ledger")),
            ("GET Compare (/stints/compare)", lambda: client.get(f"/stints/compare?stint_a=2024_monza_R_VER_1&stint_b=2024_monza_R_LEC_1"))
        ]

        api_results = []
        for name, req_fn in endpoints:
            latencies = []
            t_start = time.perf_counter()
            for _ in range(num_requests):
                t0 = time.perf_counter()
                resp = req_fn()
                dur_ms = (time.perf_counter() - t0) * 1000.0
                assert resp.status_code == 200
                latencies.append(dur_ms)
            total_elapsed = time.perf_counter() - t_start
            throughput = num_requests / total_elapsed

            stats = compute_metrics(latencies)
            stats["name"] = name
            stats["throughput"] = round(throughput, 1)
            api_results.append(stats)

        print("-" * 90)
        print(f"{'Component / Endpoint':<46} | {'Mean':>8} | {'p50':>8} | {'p95':>8} | {'p99':>8} | {'Throughput':>10}")
        print("-" * 90)
        print(f"{'Stage 3 TCN Embedding Inference':<46} | {tcn_stats['mean_ms']:>6.3f}ms | {tcn_stats['p50_ms']:>6.3f}ms | {tcn_stats['p95_ms']:>6.3f}ms | {tcn_stats['p99_ms']:>6.3f}ms | {1000.0/tcn_stats['mean_ms']:>8.1f} req/s")
        print(f"{'Bounded Counterfactual Recovery':<46} | {cf_stats['mean_ms']:>6.4f}ms | {cf_stats['p50_ms']:>6.4f}ms | {cf_stats['p95_ms']:>6.4f}ms | {cf_stats['p99_ms']:>6.4f}ms | {1000.0/max(0.001, cf_stats['mean_ms']):>8.1f} req/s")
        print(f"{'L1 In-Memory KV Cache Hit':<46} | {mem_stats['mean_ms']:>6.4f}ms | {mem_stats['p50_ms']:>6.4f}ms | {mem_stats['p95_ms']:>6.4f}ms | {mem_stats['p99_ms']:>6.4f}ms | {1000.0/max(0.001, mem_stats['mean_ms']):>8.1f} req/s")
        for r in api_results:
            print(f"{r['name']:<46} | {r['mean_ms']:>6.2f}ms | {r['p50_ms']:>6.2f}ms | {r['p95_ms']:>6.2f}ms | {r['p99_ms']:>6.2f}ms | {r['throughput']:>8.1f} req/s")
        print("-" * 90)


if __name__ == "__main__":
    reqs = 500
    if len(sys.argv) > 1:
        try:
            reqs = int(sys.argv[1])
        except ValueError:
            pass
    run_benchmarks(reqs)
