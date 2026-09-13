"""
scripts/train.py — Canonical 2024 Training Entry Point for State-Transition TDSM.
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from trackshift.tdsm.trainer import run_training_pipeline

if __name__ == "__main__":
    run_training_pipeline()
