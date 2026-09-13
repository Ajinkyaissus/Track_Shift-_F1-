"""
scripts/audit.py — Canonical 25-Phase Forensic Audit Entrypoint for TrackShift TDSM.
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from trackshift.audit import run_full_audit

if __name__ == "__main__":
    run_full_audit()
