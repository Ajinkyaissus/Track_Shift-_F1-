"""
TrackShift Real-Time Historical Telemetry & Tyre Debt Replay Simulator.
Simulates deterministic lap-by-lap race telemetry replay, real-time tyre debt accumulation,
and live interactive hypothetical sensitivity queries over WebSocket/REST.
"""

import sys
import time
import json
import asyncio
import pandas as pd
import numpy as np

from api.models import get_model_registry, BEHAVIORAL_FEATURES
from api.cache import get_cache_service, CacheKeys

DATA_DIR = "data"
LAPS_PARQUET = f"{DATA_DIR}/laps.parquet"
LEDGER_PARQUET = f"{DATA_DIR}/residual_ledger.parquet"


async def simulate_stint(stint_id: str = "2024_monza_R_VER_1", speed_multiplier: float = 1.0):
    """
    Simulates real-time historical telemetry replay for a Grand Prix stint.
    """
    print("=" * 80)
    print(f" TRACKSHIFT REAL-TIME HISTORICAL TELEMETRY REPLAY")
    print(f" Stint: {stint_id} | Speed: {speed_multiplier}x")
    print("=" * 80)

    # 1. Load real telemetry & ledger data
    laps_df = pd.read_parquet(LAPS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    stint_laps = laps_df[laps_df["stint_id"] == stint_id].sort_values("lap_number")
    stint_ledger = ledger_df[ledger_df["stint_id"] == stint_id].sort_values("lap_number")

    if stint_laps.empty:
        print(f"Error: Stint {stint_id} not found in dataset.")
        return

    registry = get_model_registry()
    cache = get_cache_service()
    await cache.initialize()

    print(f"Driver: {stint_laps.iloc[0]['driver_id']} | Compound: {stint_laps.iloc[0]['compound']}")
    print(f"Total Laps in Replay: {len(stint_laps)}")
    print("-" * 80)
    print(f"{'Lap':<5} | {'Lap Time':<10} | {'Brake Agg':<10} | {'Throttle':<10} | {'Residual':<10} | {'Cumul Debt':<12} | {'Replay Status'}")
    print("-" * 80)

    cumulative_debt = 0.0
    buffer_telemetry = []

    for idx, (_, row) in enumerate(stint_laps.iterrows()):
        lap_num = int(row["lap_number"])
        lap_time = row["lap_time"]
        brake = row["braking_aggression"]
        throttle = row["throttle_transient_smoothness"]
        
        # Match ledger residual
        ledger_row = stint_ledger[stint_ledger["lap_number"] == lap_num]
        residual = float(ledger_row["residual"].iloc[0]) if not ledger_row.empty else 0.05
        cumulative_debt += max(0.0, residual)

        buffer_telemetry.append([row[f] for f in BEHAVIORAL_FEATURES])

        # Status tag
        status = "Nominal"
        if brake > 0.40:
            status = "[!] High Brake Stress"
        elif row["kerb_usage"] > 100.0:
            status = "[!] Aggressive Kerb"

        print(f"{lap_num:<5} | {lap_time:>7.3f}s   | {brake:>8.4f}   | {throttle:>8.4f}   | {residual:>+7.4f}s  | {cumulative_debt:>8.4f}s    | {status}")

        # Live DL Behavioral Embedding generation every 5 laps
        if len(buffer_telemetry) >= 5:
            seq_arr = np.array(buffer_telemetry).T
            emb = registry.behavioral_model.generate_embedding(seq_arr)
            emb_key = CacheKeys.behavioral_embedding("v5_tcn_live", stint_id)
            await cache.set(emb_key, {"embedding": emb.tolist(), "last_lap": lap_num})

        # Simulate interval between laps (default: 0.5s in demo mode)
        interval = max(0.05, 0.5 / speed_multiplier)
        await asyncio.sleep(interval)

    print("-" * 80)
    print(f"\n[REPLAY COMPLETE] Total Accumulated Tyre Debt: {cumulative_debt:.3f}s")
    
    # Real-time hypothetical sensitivity projection
    cf_res = registry.behavioral_model.compute_counterfactual_recovery(
        linear_loss_recovery=cumulative_debt * 0.25,
        stint_length=len(stint_laps),
        deg_per_lap=0.10
    )
    print(f"\n[MODEL-BASED HYPOTHETICAL SENSITIVITY]")
    print(f"If driver reduces Braking Aggression by 25% (under model assumptions):")
    print(f"  - Estimated Hypothetical Recovery: +{cf_res['recovered_laps']} laps (95% CI: {cf_res['ci_95']})")
    print(f"  - Method: {cf_res.get('uncertainty_method', 'stint_cluster_bootstrap')}")
    print(f"  - Saturation Status: {'Bounded (Safe)' if not cf_res['is_saturated'] else 'Saturated at Physical Limit'}\n")


def main():
    stint = sys.argv[1] if len(sys.argv) > 1 else "2024_monza_R_VER_1"
    asyncio.run(simulate_stint(stint, speed_multiplier=10.0))


if __name__ == "__main__":
    main()
