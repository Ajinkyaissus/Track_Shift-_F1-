import asyncio
import csv
import os
import sys
import time
from typing import Any, Dict, List, Tuple
import httpx
import numpy as np

# Configure UTF-8 safe stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


BASE_URL = "http://127.0.0.1:8000"
PAYLOAD = {"feature": "braking_aggression", "delta_pct": -10}
CONCURRENCY_LEVELS = [10, 50, 100]
WARMUP_REQUESTS = 10
CSV_OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latency_benchmark_results.csv")


async def get_target_stint_url(client: httpx.AsyncClient) -> Tuple[str, str]:
    """Fetch a real stint_id dynamically from the active API."""
    try:
        races_resp = await client.get(f"{BASE_URL}/races")
        if races_resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch races: HTTP {races_resp.status_code}")
        races = races_resp.json()
        if not races:
            raise RuntimeError("No races found in database. Run seed.py first.")

        for race in races:
            race_id = race.get("race_id")
            stints_resp = await client.get(f"{BASE_URL}/sessions/{race_id}/stints")
            if stints_resp.status_code == 200:
                stints = stints_resp.json()
                if stints and len(stints) > 0:
                    stint_id = stints[0]["stint_id"]
                    url = f"{BASE_URL}/stints/{stint_id}/counterfactual"
                    return stint_id, url

        raise RuntimeError("No valid stints found for any race.")
    except httpx.ConnectError:
        print(f"\n[ERROR] Could not connect to {BASE_URL}. Ensure the backend is running (`npm run api`).", file=sys.stderr)
        sys.exit(1)


async def run_warmup(client: httpx.AsyncClient, url: str, count: int = WARMUP_REQUESTS) -> None:
    """Run sequential warmup requests to JIT paths, connection pools, and in-memory caches."""
    print(f"[*] Running {count} sequential warmup requests...")
    for i in range(count):
        resp = await client.post(url, json=PAYLOAD)
        if resp.status_code != 200:
            print(f"    [!] Warmup request {i+1} returned HTTP {resp.status_code}", file=sys.stderr)
    print("    Warmup complete.\n")


async def fire_concurrent_batch(
    client: httpx.AsyncClient,
    url: str,
    concurrency_n: int
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Fire exactly N requests simultaneously in-flight via asyncio.gather.
    Measures individual client-side wall-clock request duration as well as total batch time.
    """
    results: List[Dict[str, Any]] = []

    async def single_request(req_id: int):
        t0 = time.perf_counter()
        try:
            resp = await client.post(url, json=PAYLOAD)
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0
            return {
                "concurrency_level": concurrency_n,
                "request_id": req_id,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
                "error": "" if resp.status_code == 200 else f"HTTP_{resp.status_code}",
                "server_internal_ms": resp.json().get("measured_latency_ms") if resp.status_code == 200 else None
            }
        except Exception as exc:
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0
            return {
                "concurrency_level": concurrency_n,
                "request_id": req_id,
                "status_code": 0,
                "latency_ms": latency_ms,
                "error": type(exc).__name__,
                "server_internal_ms": None
            }

    # All requests initiated simultaneously and gathered in-flight
    batch_start = time.perf_counter()
    tasks = [single_request(i + 1) for i in range(concurrency_n)]
    results = await asyncio.gather(*tasks)
    batch_total_time = time.perf_counter() - batch_start

    return results, batch_total_time


def print_comparison_table(metrics: Dict[int, Dict[str, Any]]) -> None:
    """Display clean side-by-side comparative table for hackathon presentation / audit defense."""
    col_width = 18
    header = f"{'Metric':<32}" + "".join([f"{f'N = {n} Concurrent':^{col_width}}" for n in CONCURRENCY_LEVELS])
    divider = "=" * len(header)
    sub_divider = "-" * len(header)

    print(divider)
    print("🏆 TRACKSHIFT CONCURRENT LOAD LATENCY BENCHMARK")
    print(f"Target: POST {BASE_URL}/stints/{{stint_id}}/counterfactual")
    print(divider)
    print(header)
    print(sub_divider)

    rows = [
        ("Total Requests Fired", lambda m: f"{m['total_requests']}"),
        ("Successful (HTTP 200)", lambda m: f"{m['successful_requests']}"),
        ("Errors / Timeouts", lambda m: f"{m['errors']}"),
        ("Error Rate (%)", lambda m: f"{m['error_rate']:.2f}%"),
        ("Batch Wall-Clock Time (s)", lambda m: f"{m['batch_time_sec']:.3f} s"),
        ("Throughput (req/sec)", lambda m: f"{m['throughput_rps']:.1f} rps"),
        ("P50 (Median) Latency (ms)", lambda m: f"{m['p50']:.2f} ms"),
        ("P95 Latency (ms)", lambda m: f"{m['p95']:.2f} ms"),
        ("P99 Latency (ms)", lambda m: f"{m['p99']:.2f} ms"),
        ("Min Latency (ms)", lambda m: f"{m['min']:.2f} ms"),
        ("Max Latency (ms)", lambda m: f"{m['max']:.2f} ms"),
    ]

    for label, getter in rows:
        row_str = f"{label:<32}" + "".join([f"{getter(metrics[n]):^{col_width}}" for n in CONCURRENCY_LEVELS])
        print(row_str)

    print(divider)
    print("SLA Target: P95 < 250 ms across all concurrency tiers")
    all_passed = all(metrics[n]["p95"] < 250.0 for n in CONCURRENCY_LEVELS) and all(metrics[n]["errors"] == 0 for n in CONCURRENCY_LEVELS)
    print(f"OVERALL STATUS: {'✅ PASSED ALL CONCURRENCY SLAS' if all_passed else '❌ FAILED SLA'}")
    print(divider + "\n")


def save_to_csv(all_raw_results: List[Dict[str, Any]], filepath: str) -> None:
    """Save all individual raw measurements to CSV for plotting and post-analysis."""
    fieldnames = ["concurrency_level", "request_id", "status_code", "latency_ms", "server_internal_ms", "error"]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_raw_results:
            writer.writerow(row)
    print(f"[*] Raw latency data saved to: {filepath}")


async def main():
    limits = httpx.Limits(
        max_connections=100,
        max_keepalive_connections=100
    )

    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        print(f"[*] Discovering target stint from {BASE_URL}...")
        stint_id, url = await get_target_stint_url(client)
        print(f"    Target Stint ID: {stint_id}")
        print(f"    Endpoint URL:    {url}")
        print(f"    Payload:         {PAYLOAD}\n")

        # 1. Warmup
        await run_warmup(client, url, count=WARMUP_REQUESTS)

        # 2. Run concurrent batches
        all_raw_results: List[Dict[str, Any]] = []
        metrics_by_level: Dict[int, Dict[str, Any]] = {}

        for n in CONCURRENCY_LEVELS:
            print(f"[*] Launching batch of N={n} simultaneous in-flight requests (asyncio.gather)...")
            raw_batch, batch_time = await fire_concurrent_batch(client, url, n)
            all_raw_results.extend(raw_batch)

            latencies = [r["latency_ms"] for r in raw_batch if r["status_code"] == 200]
            errors = sum(1 for r in raw_batch if r["status_code"] != 200)

            if latencies:
                p50 = float(np.percentile(latencies, 50))
                p95 = float(np.percentile(latencies, 95))
                p99 = float(np.percentile(latencies, 99))
                min_lat = float(np.min(latencies))
                max_lat = float(np.max(latencies))
            else:
                p50 = p95 = p99 = min_lat = max_lat = 0.0

            throughput = n / batch_time if batch_time > 0 else 0.0

            metrics_by_level[n] = {
                "total_requests": n,
                "successful_requests": len(latencies),
                "errors": errors,
                "error_rate": (errors / n) * 100.0,
                "batch_time_sec": batch_time,
                "throughput_rps": throughput,
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "min": min_lat,
                "max": max_lat,
            }

            # Brief pause between tiers to allow server event loop to settle
            await asyncio.sleep(0.5)

        # 3. Print side-by-side comparative table
        print("\n")
        print_comparison_table(metrics_by_level)

        # 4. Save raw CSV
        save_to_csv(all_raw_results, CSV_OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())
