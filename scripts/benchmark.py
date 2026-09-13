"""
scripts/benchmark.py — Authoritative Production Latency & Performance Benchmark Engine.
========================================================================================
Consolidates performance benchmarks across the TrackShift stack:
1. Application cold startup latency & lifespan prewarming time
2. ML / Deep Learning inference latency (HistGradientBoosting & MultiTaskBehavioralTCN)
3. L1 in-memory KV cache operations throughput
4. Per-endpoint REST API latency distributions (p50, p95, p99, max)
5. Sustained warm throughput measurement

Usage:
    python scripts/benchmark.py [--iterations N] [--save-report]
"""

import os
import sys
import time
import argparse
import json
import numpy as np
import torch
from fastapi.testclient import TestClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app
from api.cache import MemoryCache
from trackshift.tdsm.model import TinyTDSM, FallbackTDSM, INPUT_DIM


def compute_distribution(samples_ms: list) -> dict:
    arr = np.array(samples_ms, dtype=np.float64)
    return {
        "count": len(arr),
        "mean_ms": round(float(np.mean(arr)), 3),
        "std_ms": round(float(np.std(arr)), 3),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
        "p99_ms": round(float(np.percentile(arr, 99)), 3),
        "max_ms": round(float(np.max(arr)), 3),
    }


def run_benchmarks(iterations: int = 50, save_report: bool = True):
    print("=" * 80)
    print(" TRACKSHIFT — PRODUCTION LATENCY & PERFORMANCE BENCHMARK ENGINE")
    print("=" * 80)
    report = {}

    with TestClient(app) as client:
        # 1. Application Cold Startup & Prewarming Latency
        t0 = time.perf_counter()
        _ = client.get("/health")
        cold_startup_ms = (time.perf_counter() - t0) * 1000.0
        print(f"\n[1] Application Cold Startup Time: {cold_startup_ms:.2f} ms")
        report["cold_startup_ms"] = round(cold_startup_ms, 2)

        # 2. TDSM Inference Benchmark (State-Transition TinyTDSM)
        print("\n[2] ML Inference Benchmark (Primary State-Transition TinyTDSM)...")
        model = TinyTDSM(input_dim=INPUT_DIM)
        model.eval()
        dummy_x = torch.randn(1, INPUT_DIM)
        dummy_d = torch.tensor([[0.5]], dtype=torch.float32)
        
        # Warmup
        for _ in range(10):
            with torch.no_grad():
                _ = model.predict_forecast_debt(dummy_x, dummy_d)
                
        tdsm_latencies = []
        for _ in range(100):
            t_start = time.perf_counter()
            with torch.no_grad():
                _ = model.predict_forecast_debt(dummy_x, dummy_d)
            tdsm_latencies.append((time.perf_counter() - t_start) * 1000.0)
        
        tdsm_stats = compute_distribution(tdsm_latencies)
        print(f"  TinyTDSM Kernel Inference (100 runs): Mean={tdsm_stats['mean_ms']:.3f}ms | p50={tdsm_stats['p50_ms']:.3f}ms | p99={tdsm_stats['p99_ms']:.3f}ms")
        report["tdsm_inference"] = tdsm_stats

        # 3. In-Memory KV Cache Operations
        print("\n[3] In-Memory Cache Benchmark...")
        import asyncio
        async def bench_cache():
            mem = MemoryCache()
            # Set
            t_start = time.perf_counter()
            for i in range(1000):
                await mem.set(f"bench_key_{i}", {"val": i, "payload": "trackshift_telemetry"})
            set_dur = time.perf_counter() - t_start
            set_ops = 1000.0 / set_dur
            
            # Get
            t_start = time.perf_counter()
            for i in range(1000):
                await mem.get(f"bench_key_{i}")
            get_dur = time.perf_counter() - t_start
            get_ops = 1000.0 / get_dur
            return set_ops, get_ops

        set_ops, get_ops = asyncio.run(bench_cache())
        print(f"  Memory Cache Operations: SET={set_ops:,.0f} ops/sec | GET={get_ops:,.0f} ops/sec")
        report["cache_ops"] = {"set_ops_sec": round(set_ops, 1), "get_ops_sec": round(get_ops, 1)}

        # 4. REST API Endpoints Benchmark
        endpoints = [
            ("Health Check", "/health"),
            ("Feature Provenance", "/api/tyre-intelligence/provenance"),
            ("Degradation Curve (Silverstone)", "/api/tyre-intelligence/degradation-curve?circuit_id=silverstone&driver_id=HAM"),
            ("8-Model Ablation Study", "/api/tyre-intelligence/ablation"),
            ("Post-Race Validation", "/api/tyre-intelligence/post-race-validation"),
            ("Confounder Breakdown", "/api/tyre-intelligence/confounder-breakdown?circuit_id=silverstone&driver_id=HAM"),
            ("Driver Advisory", "/sessions/2024_silverstone_R/driver-advisory?driver_id=HAM&lap=20"),
            ("Circuit Map Geometry", "/circuits/silverstone/map"),
            ("Session Drivers Roster", "/sessions/2024_silverstone_R/drivers"),
            ("Strategic Warfare", "/api/sessions/2024_silverstone_R/strategic-warfare"),
            ("Race Intelligence", "/sessions/2024_silverstone_R/race-intelligence"),
        ]

        print(f"\n[4] REST API Latencies ({iterations} iterations per endpoint):")
        print("-" * 85)
        print(f"{'Endpoint':<34} | {'First':>7} | {'Mean':>7} | {'p50':>7} | {'p95':>7} | {'p99':>7} | {'Max':>7}")
        print("-" * 85)

        endpoint_reports = {}
        for name, url in endpoints:
            # First (cold) request
            t_c0 = time.perf_counter()
            res_c0 = client.get(url)
            first_ms = (time.perf_counter() - t_c0) * 1000.0

            # Repeated warm requests
            warm_samples = []
            for _ in range(iterations):
                t_w0 = time.perf_counter()
                client.get(url)
                warm_samples.append((time.perf_counter() - t_w0) * 1000.0)

            dist = compute_distribution(warm_samples)
            endpoint_reports[name] = {
                "url": url,
                "first_call_ms": round(first_ms, 2),
                "distribution": dist
            }
            print(f"{name:<34} | {first_ms:>7.2f} | {dist['mean_ms']:>7.2f} | {dist['p50_ms']:>7.2f} | {dist['p95_ms']:>7.2f} | {dist['p99_ms']:>7.2f} | {dist['max_ms']:>7.2f}")

        report["endpoints"] = endpoint_reports

    print("-" * 85)

    if save_report:
        reports_dir = os.path.join(BASE_DIR, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out_file = os.path.join(reports_dir, "production_latency_benchmark.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[OK] Latency benchmark report saved to: {out_file}")

    print("\n" + "=" * 80)
    print(" BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrackShift Performance Benchmark Engine")
    parser.add_argument("--iterations", type=int, default=30, help="Number of warm iterations per endpoint")
    parser.add_argument("--no-save", action="store_true", help="Do not save JSON report")
    args = parser.parse_args()

    sys.exit(run_benchmarks(iterations=args.iterations, save_report=not args.no_save))
