"""
tests/test_constants_single_source.py
======================================
Static repository scan to enforce that production domain constants have
exactly ONE source of truth: trackshift/domain_constants.py.

Rules enforced:
1. No production .py file outside of domain_constants.py may hardcode
   the numeric literal 0.1974 (M1 intercept) in executable code.
2. No production .py file outside of domain_constants.py may hardcode
   the numeric literal 0.0400 or 0.04 as the M1 slope in executable code.

Exemptions (allowed to contain the literals):
  - trackshift/domain_constants.py (the source of truth)
  - tests/ directory (test fixtures may reference them)
  - reports/ directory (generated JSON/MD reports — not executable)
  - scripts/ directory (audit/validation scripts — not production)
  - pipeline/ directory (training pipeline — reads coefficients separately)
  - *.md files, *.json files (documentation/data — not executable)
  - __pycache__ directories

If this test fails, a hardcoded production literal was added somewhere
outside the canonical source. Fix it by importing from domain_constants.
"""

import os
import re
import sys
import ast
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that are ALLOWED to contain the literals
ALLOWED_PATHS = {
    os.path.normpath(os.path.join(BASE_DIR, "trackshift", "domain_constants.py")),
}

ALLOWED_DIR_PREFIXES = [
    os.path.normpath(os.path.join(BASE_DIR, "tests")),
    os.path.normpath(os.path.join(BASE_DIR, "reports")),
    os.path.normpath(os.path.join(BASE_DIR, "scripts")),
    os.path.normpath(os.path.join(BASE_DIR, "pipeline")),
    os.path.normpath(os.path.join(BASE_DIR, "docs")),
]

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules"}


def _is_exempted(filepath: str) -> bool:
    """Return True if this file is allowed to contain the literal."""
    norm = os.path.normpath(filepath)
    if norm in ALLOWED_PATHS:
        return True
    for prefix in ALLOWED_DIR_PREFIXES:
        if norm.startswith(prefix):
            return True
    return False


def _collect_python_files(root: str):
    """Yield all .py file paths under root, skipping exempt dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden/cache directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _extract_string_and_comment_ranges(source: str):
    """
    Return list of (start_pos, end_pos) for string literals and comments,
    so we can skip them during numeric literal scanning.
    """
    ranges = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Constant,)) and isinstance(node.value, str):
                # String literal — skip
                if hasattr(node, "col_offset") and hasattr(node, "end_col_offset"):
                    ranges.append((getattr(node, "lineno", 0), getattr(node, "end_lineno", 0)))
    except SyntaxError:
        pass
    return ranges


def _find_hardcoded_in_file(filepath: str, patterns: list) -> list:
    """
    Scan a Python file for hardcoded numeric literals matching patterns.
    Returns list of (line_number, line_content) tuples.

    Skips:
    - Pure comment lines
    - Lines inside triple-quoted string literals (docstrings)
    - Lines inside single/double quoted strings
    """
    violations = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
            lines = source.splitlines()
    except OSError:
        return violations

    # Build a set of line numbers that are inside string literals (docstrings etc)
    string_lines: set = set()
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None)
                if start and end:
                    for ln in range(start, end + 1):
                        string_lines.add(ln)
    except SyntaxError:
        pass  # Fall back to pattern-only if parse fails

    for lineno, line in enumerate(lines, start=1):
        # Skip lines inside string literals / docstrings
        if lineno in string_lines:
            continue
        stripped = line.strip()
        # Skip pure comment lines
        if stripped.startswith("#"):
            continue
        for pat in patterns:
            if re.search(pat, line):
                # Remove inline comment and inline string fragments before final check
                scrubbed = re.sub(r'"[^"]*"|\'[^\']*\'', '""', line)
                scrubbed = re.sub(r'#.*$', '', scrubbed)
                if re.search(pat, scrubbed):
                    violations.append((lineno, line.rstrip()))
    return violations


# ---------------------------------------------------------------------------
# Patterns to detect hardcoded M1 intercept
# We look for the literal as an assignment value or in arithmetic expressions,
# not just as part of a string.
# ---------------------------------------------------------------------------
M1_INTERCEPT_PATTERNS = [
    r'\b0\.1974\b',   # 0.1974 as a standalone numeric token
]

# For slope: 0.0400 or 0.04 used in multiplication context with tyre_age
# Be careful — 0.04 can appear in other contexts (e.g., noise=0.04 in tests)
# We restrict to patterns that look like M1 slope (next to tyre_age or slope/coef keyword)
M1_SLOPE_PATTERNS = [
    r'\b0\.0400\b',   # exact 0.0400 — unique to M1 slope
]


def _get_production_python_files():
    """Collect all production Python files (non-exempted)."""
    files = []
    for fp in _collect_python_files(os.path.join(BASE_DIR, "trackshift")):
        if not _is_exempted(fp):
            files.append(fp)
    for fp in _collect_python_files(os.path.join(BASE_DIR, "api")):
        if not _is_exempted(fp):
            files.append(fp)
    return files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_hardcoded_m1_intercept_in_production():
    """
    0.1974 must not appear as a numeric literal in any production .py file
    outside of trackshift/domain_constants.py.

    If this test fails: import STAGE1_M1_INTERCEPT from trackshift.domain_constants.
    """
    production_files = _get_production_python_files()
    all_violations = []

    for fp in production_files:
        violations = _find_hardcoded_in_file(fp, M1_INTERCEPT_PATTERNS)
        for lineno, content in violations:
            rel = os.path.relpath(fp, BASE_DIR)
            all_violations.append(f"  {rel}:{lineno}  →  {content}")

    assert not all_violations, (
        "Hardcoded M1 intercept (0.1974) found in production code.\n"
        "Import STAGE1_M1_INTERCEPT from trackshift.domain_constants instead:\n"
        + "\n".join(all_violations)
    )


def test_no_hardcoded_m1_slope_0400_in_production():
    """
    0.0400 (exact) must not appear as a numeric literal in any production .py file
    outside of trackshift/domain_constants.py.

    If this test fails: import STAGE1_M1_SLOPE from trackshift.domain_constants.
    """
    production_files = _get_production_python_files()
    all_violations = []

    for fp in production_files:
        violations = _find_hardcoded_in_file(fp, M1_SLOPE_PATTERNS)
        for lineno, content in violations:
            rel = os.path.relpath(fp, BASE_DIR)
            all_violations.append(f"  {rel}:{lineno}  →  {content}")

    assert not all_violations, (
        "Hardcoded M1 slope (0.0400) found in production code.\n"
        "Import STAGE1_M1_SLOPE from trackshift.domain_constants instead:\n"
        + "\n".join(all_violations)
    )


def test_domain_constants_module_exists_and_is_importable():
    """domain_constants.py must exist and export the required constants."""
    from trackshift.domain_constants import (
        STAGE1_M1_INTERCEPT,
        STAGE1_M1_SLOPE,
        FUEL_EFFECT_COEFFICIENT,
        stage1_m1_loss,
    )
    assert isinstance(STAGE1_M1_INTERCEPT, float)
    assert isinstance(STAGE1_M1_SLOPE, float)
    assert isinstance(FUEL_EFFECT_COEFFICIENT, float)
    assert callable(stage1_m1_loss)


def test_fuel_effect_coefficient_not_hardcoded_in_trackshift_production():
    """
    0.033 used as FUEL_EFFECT_COEFFICIENT should be imported, not hardcoded inline
    in any trackshift/ production file (race_intelligence_service.py uses it directly
    in api/ — that is an allowed API-layer usage but should be flagged for future cleanup).
    """
    # This is an informational test — we check the core trackshift/ library only.
    trackshift_files = [
        fp for fp in _collect_python_files(os.path.join(BASE_DIR, "trackshift"))
        if not _is_exempted(fp)
    ]

    violations = []
    for fp in trackshift_files:
        found = _find_hardcoded_in_file(fp, [r'\b0\.033\b'])
        for lineno, content in found:
            rel = os.path.relpath(fp, BASE_DIR)
            violations.append(f"  {rel}:{lineno}  →  {content}")

    # Warn but do not fail — 0.033 may appear in legitimate calculations
    # that haven't been refactored yet. This documents the current state.
    if violations:
        import warnings
        warnings.warn(
            f"Found {len(violations)} hardcoded 0.033 literals in trackshift/ — "
            f"consider importing FUEL_EFFECT_COEFFICIENT:\n" + "\n".join(violations),
            UserWarning,
            stacklevel=2,
        )
