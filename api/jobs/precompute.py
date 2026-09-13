"""
TrackShift Offline Precompute & KV Cache Prewarming Pipeline.
Precalculates and caches circuit maps, DL behavioral embeddings,
stint ledgers, attribution decompositions, and standard counterfactual projections.
"""

import os
import sys
import math
import time
import asyncio
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.cache import CacheKeys, get_cache_service, DATA_VERSION, LEDGER_VERSION, MAP_VERSION, TELEMETRY_VERSION
from api.models import get_model_registry, BEHAVIORAL_FEATURES
DB_PATH = os.path.join(BASE_DIR, "api", "tyredebt.db")
DATA_DIR = os.path.join(BASE_DIR, "data")
GEOMETRY_PARQUET = os.path.join(DATA_DIR, "circuit_geometry.parquet")
LEDGER_PARQUET = os.path.join(DATA_DIR, "residual_ledger.parquet")
LAPS_PARQUET = os.path.join(DATA_DIR, "laps.parquet")


async def run_precompute() -> dict:
    """Executes the precomputation and cache prewarming pipeline."""
    start_time = time.perf_counter()
    cache = get_cache_service()
    await cache.initialize()
    
    registry = get_model_registry()
    stage1_version = registry.get_stage_version(1)
    stage3_version = registry.get_stage_version(3)

    # 1. Load SQLite metadata
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT track_id, name, country, country_code, location, rotation FROM tracks")
    tracks = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start,
               r.track_id, (s.end_lap - s.start_lap + 1) as stint_len
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
        WHERE s.is_valid = 1
    """)
    stints_meta = [dict(r) for r in cursor.fetchall()]
    stint_track_map = {s["stint_id"]: s["track_id"] for s in stints_meta}
    stint_lengths = {s["stint_id"]: max(5, s["stint_len"] if s["stint_len"] else 20) for s in stints_meta}

    cursor.execute("SELECT circuit_id, corner_number, corner_letter, x, y, angle, distance FROM circuit_corners ORDER BY circuit_id, corner_number")
    circuit_corners: dict = {}
    for r in cursor.fetchall():
        cid = r["circuit_id"]
        if cid not in circuit_corners:
            circuit_corners[cid] = []
        circuit_corners[cid].append(dict(r))

    cursor.execute("SELECT driver_id, full_name, team, reputation_tag FROM drivers")
    drivers_meta = {d["driver_id"]: dict(d) for d in cursor.fetchall()}

    conn.close()

    # 2. Precompute Circuit Maps
    maps_cached = 0
    if os.path.exists(GEOMETRY_PARQUET):
        geom_df = pd.read_parquet(GEOMETRY_PARQUET)
        for track in tracks:
            cid = track["track_id"]
            track_geom = geom_df[geom_df["circuit_id"] == cid]
            if not track_geom.empty:
                pts = track_geom[["x_rot", "y_rot", "X", "Y", "Distance", "Speed", "Throttle", "Brake"]].rename(
                    columns={"X": "x", "Y": "y", "Distance": "distance", "Speed": "speed", "Throttle": "throttle", "Brake": "brake"}
                ).to_dict(orient="records")
                corners = circuit_corners.get(cid, [])
                
                payload = {
                    "circuit_id": cid,
                    "track_id": cid,
                    "name": track["name"],
                    "country": track["country"],
                    "location": track["location"],
                    "rotation": track["rotation"],
                    "points_count": len(pts),
                    "corners_count": len(corners),
                    "points": pts,
                    "corners": corners
                }
                key = CacheKeys.circuit_map(cid, DATA_VERSION, MAP_VERSION)
                await cache.set(key, payload)
                maps_cached += 1

    # 3. Precompute Ledgers
    ledgers_cached = 0
    evaluated_laps = 0
    stint_ledgers = {}
    stint_avg_loss_per_lap = {}

    if os.path.exists(LEDGER_PARQUET):
        ledger_df = pd.read_parquet(LEDGER_PARQUET)
        evaluated_laps = len(ledger_df)

        for stint_id, group in ledger_df.groupby("stint_id"):
            series = group[["lap_number", "residual", "cumulative_debt"]].to_dict(orient="records")
            stint_ledgers[stint_id] = series
            total_debt = round(series[-1]["cumulative_debt"], 4) if len(series) > 0 else 0.0

            payload = {
                "stint_id": stint_id,
                "model_version": stage1_version,
                "total_debt_seconds": total_debt,
                "series": series
            }
            key = CacheKeys.stint_ledger(stint_id, LEDGER_VERSION)
            await cache.set(key, payload)
            ledgers_cached += 1

            # Calculate deg rate
            if len(group) >= 2 and "predicted_lap_time_loss" in group.columns:
                group_sorted = group.sort_values("lap_number")
                first = group_sorted.iloc[0]
                last = group_sorted.iloc[-1]
                dn = last["lap_number"] - first["lap_number"]
                rate = (last["predicted_lap_time_loss"] - first["predicted_lap_time_loss"]) / dn if dn != 0 else 0.1
                stint_avg_loss_per_lap[stint_id] = float(rate) if rate != 0 else 0.1
            else:
                stint_avg_loss_per_lap[stint_id] = 0.1

    # 4. Precompute DL Embeddings & Attributions
    embeddings_cached = 0
    attributions_cached = 0
    counterfactuals_cached = 0

    if os.path.exists(LAPS_PARQUET):
        laps_df = pd.read_parquet(LAPS_PARQUET)
        grouped_laps = laps_df.groupby("stint_id")
        means_df = laps_df.groupby("stint_id")[BEHAVIORAL_FEATURES].mean()

        for stint_id, lap_group in grouped_laps:
            # DL Behavioral Embedding
            seq = lap_group[BEHAVIORAL_FEATURES].to_numpy()
            try:
                emb = registry.get_or_generate_embedding(stint_id, seq)
            except ValueError:
                emb = None
            if emb is not None:
                emb_key = CacheKeys.behavioral_embedding(stage3_version, stint_id, TELEMETRY_VERSION)
                await cache.set(emb_key, {"stint_id": stint_id, "embedding": emb, "embedding_dim": len(emb)})
                embeddings_cached += 1

            # Classical + Hybrid Attribution
            if stint_id in means_df.index:
                means = means_df.loc[stint_id].to_dict()
                track_id = stint_track_map.get(stint_id)
                
                attribution = []
                total_abs_contrib = 0.0
                contribs = {}

                for feature, avg_val in means.items():
                    val = 0.0 if math.isnan(avg_val) else float(avg_val)
                    coef = registry.get_coefficient(stage3_version, feature, track_id)
                    contrib = coef * val
                    contribs[feature] = contrib
                    total_abs_contrib += abs(contrib)

                if total_abs_contrib == 0:
                    total_abs_contrib = 1.0

                for feature, avg_val in means.items():
                    val = 0.0 if math.isnan(avg_val) else float(avg_val)
                    contrib = contribs[feature]
                    pct = (abs(contrib) / total_abs_contrib) * 100.0
                    coef = registry.get_coefficient(stage3_version, feature, track_id)

                    attribution.append({
                        "feature": feature,
                        "feature_name": feature.replace("_", " ").title(),
                        "contribution": round(contrib, 4),
                        "share_pct": round(pct, 2),
                        "pct_contribution": round(pct, 2),
                        "coefficient": round(coef, 6),
                        "mean_value": round(val, 4),
                        "unit": f"seconds debt per 1 unit {feature}"
                    })

                deg_per_lap = stint_avg_loss_per_lap.get(stint_id, 0.1)
                attr_payload = {
                    "stint_id": stint_id,
                    "model_version": stage3_version,
                    "algorithm": "hybrid_tcn_ridge_attribution",
                    "behavioral_embedding_dim": len(emb) if emb is not None else 0,
                    "deg_per_lap": round(deg_per_lap, 4),
                    "attribution": attribution
                }
                attr_key = CacheKeys.stint_attribution(stint_id, stage3_version)
                await cache.set(attr_key, attr_payload)
                attributions_cached += 1

                # Standard Counterfactual Grid (-25%, -10%, +10%, +25% on primary features)
                stint_len = stint_lengths.get(stint_id, 20)
                for feat in BEHAVIORAL_FEATURES:
                    for delta in [-25.0, -10.0, 10.0, 25.0]:
                        avg_val = means.get(feat, 0.0)
                        if math.isnan(avg_val):
                            avg_val = 0.0
                        coef = registry.get_coefficient(stage3_version, feat, track_id)
                        seconds_rec = -(coef * (delta / 100.0) * avg_val)
                        
                        cf_res = registry.behavioral_model.compute_counterfactual_recovery(
                            linear_loss_recovery=seconds_rec,
                            stint_length=stint_len,
                            deg_per_lap=deg_per_lap
                        )
                        cf_payload = {
                            "feature": feat,
                            "delta_pct": delta,
                            "recovered_laps": cf_res["recovered_laps"],
                            "ci_95": cf_res["ci_95"],
                            "uncertainty_margin": cf_res["uncertainty_margin"],
                            "is_saturated": cf_res["is_saturated"],
                            "model_version": stage3_version,
                            "compute_path": "precomputed_kv_lookup"
                        }
                        cf_key = CacheKeys.stint_counterfactual(stint_id, stage3_version, feat, delta)
                        await cache.set(cf_key, cf_payload)
                        counterfactuals_cached += 1

    elapsed = time.perf_counter() - start_time

    summary = {
        "circuits": len(tracks),
        "stints": len(stints_meta),
        "evaluated_laps": evaluated_laps,
        "embeddings_generated": embeddings_cached,
        "attributions_cached": attributions_cached,
        "counterfactuals_cached": counterfactuals_cached,
        "maps_cached": maps_cached,
        "elapsed_seconds": round(elapsed, 2)
    }

    print("\nTrackShift Precompute")
    print("---------------------")
    print(f"Circuits:              {summary['circuits']}")
    print(f"Stints:                {summary['stints']}")
    print(f"Evaluated laps:        {summary['evaluated_laps']}")
    print(f"Embeddings generated:  {summary['embeddings_generated']}")
    print(f"Attributions cached:   {summary['attributions_cached']}")
    print(f"Counterfactuals cached: {summary['counterfactuals_cached']}")
    print(f"Maps cached:           {summary['maps_cached']}")
    print(f"Elapsed time:          {summary['elapsed_seconds']}s")
    print("\nStatus: SUCCESS\n")

    return summary


def main():
    asyncio.run(run_precompute())


if __name__ == "__main__":
    main()
