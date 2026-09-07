import subprocess
import time
import httpx
import numpy as np
import sys
import os
import asyncio

async def fire_requests(url, payload, count, concurrency=50):
    """
    Fire `count` POST requests with bounded concurrency of `concurrency` at a time.
    Using httpx.AsyncClient with a connection limit prevents OS-level TCP exhaustion
    that occurs when firing 500 simultaneous raw connections on a local machine.
    """
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency
    )
    latencies = []
    errors = 0

    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        sem = asyncio.Semaphore(concurrency)

        async def single_request(i):
            nonlocal errors
            async with sem:
                # Record t0 INSIDE the semaphore — we measure the actual HTTP
                # round-trip time, not the queue-wait time before the request fires.
                t0 = time.perf_counter()
                try:
                    res = await client.post(url, json=payload)
                    t1 = time.perf_counter()
                    if res.status_code == 200:
                        latencies.append((t1 - t0) * 1000)
                    else:
                        errors += 1
                        print(f"  Request {i}: HTTP {res.status_code}")
                except Exception as exc:
                    errors += 1
                    print(f"  Request {i}: {type(exc).__name__}: {exc}")

        tasks = [single_request(i) for i in range(count)]
        await asyncio.gather(*tasks)

    return latencies, errors

def run_latency_test():
    # Start the uvicorn server in a subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # On Windows, single worker async event loop handles concurrent in-memory requests without IPC serialization overhead
    server_process = subprocess.Popen(
        ["uvicorn", "api.main:app", "--port", "8000", "--workers", "1", "--no-access-log", "--log-level", "warning"],
        env=env
    )

    # Poll until server is ready (up to 30 s)
    ready = False
    for _ in range(30):
        try:
            resp = httpx.get("http://127.0.0.1:8000/races")
            if resp.status_code == 200:
                ready = True
                break
        except httpx.RequestError:
            pass
        time.sleep(1)

    if not ready:
        print("Server failed to start in time.", file=sys.stderr)
        server_process.terminate()
        server_process.wait()
        sys.exit(1)

    try:
        # Find a valid stint_id
        races = httpx.get("http://127.0.0.1:8000/races").json()
        if not races:
            print("No races found. Run seed.py first.", file=sys.stderr)
            return

        stint_id = None
        for race in races:
            race_id = race['race_id']
            stints = httpx.get(f"http://127.0.0.1:8000/sessions/{race_id}/stints").json()
            if stints:
                stint_id = stints[0]['stint_id']
                break

        if not stint_id:
            print("No stints found. Run seed.py first.", file=sys.stderr)
            return

        payload = {"feature": "braking_aggression", "delta_pct": -10}
        url = f"http://127.0.0.1:8000/stints/{stint_id}/counterfactual"

        # Warm up connection pool and JIT paths
        for _ in range(10):
            httpx.post(url, json=payload, timeout=5.0)

        concurrency = 20
        print(f"Starting 500 requests (concurrency={concurrency}) against {url}...")
        latencies, errors = asyncio.run(fire_requests(url, payload, count=500, concurrency=concurrency))

        print(f"\nResults:")
        print(f"  Total:      500")
        print(f"  Successful: {len(latencies)}")
        print(f"  Errors:     {errors}")

        if not latencies:
            print("FAILED: No successful requests.", file=sys.stderr)
            sys.exit(1)

        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        print(f"  P50 latency: {p50:.2f} ms")
        print(f"  P95 latency: {p95:.2f} ms")
        print(f"  P99 latency: {p99:.2f} ms")

        if p95 > 250.0:
            print(f"\nFAILED: P95 latency {p95:.2f} ms exceeds 250 ms SLA.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\nPASSED: P95 latency {p95:.2f} ms is within 250 ms SLA.")

    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    run_latency_test()
