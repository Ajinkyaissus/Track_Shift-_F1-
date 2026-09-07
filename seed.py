"""
seed.py — Populate the Tyre Degradation Intelligence database, feature parquet files,
and train genuine ML models (HistGradientBoosting Baseline & Ridge Attribution) from
real Formula 1 telemetry across multiple races, drivers, and tyre compounds.

Run from project root:
    python seed.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pipeline.build_real_dataset import (
    init_database,
    build_multi_race_stints,
    extract_all_features,
    train_and_register_models
)

def run_seed():
    print("=================================================================")
    print("  TYRE DEBT INTELLIGENCE — DATASET SEED & REAL MODEL TRAINING   ")
    print("=================================================================")
    init_database()
    build_multi_race_stints()
    extract_all_features()
    train_and_register_models()
    print("\n=================================================================")
    print("  SEED COMPLETE: Genuine F1 telemetry and trained ML models ready")
    print("=================================================================")

if __name__ == "__main__":
    run_seed()
