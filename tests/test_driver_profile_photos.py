"""
tests/test_driver_profile_photos.py — Comprehensive Test Suite for Real Driver Profile Photos.

Verifies:
1. Deterministic Photo Mapping: VER -> /drivers/max_verstappen.webp, NOR -> /drivers/lando_norris.webp.
2. Substitute Drivers: BEA, LAW, COL, DOO, RIC, SAR map to their respective authentic portraits.
3. Order & Position Independence: Profile photos are linked strictly to driver_id / abbreviation, never array index or race position.
4. Session Adaptability: Changing sessions maintains correct driver-to-photo resolution for session rosters.
5. Fallback Robustness: Unrecognized drivers receive /drivers/fallback_driver.webp and analytics continue working seamlessly.
6. Asset Integrity: Every mapped WebP file exists physically in frontend/public/drivers/.
7. No Duplicate Photo Collisions across different drivers.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app
from api.services.circuits_service import get_driver_profile_image, DRIVER_SLUG_MAP

client = TestClient(app)
PUBLIC_DRIVERS_DIR = os.path.join(BASE_DIR, "frontend", "public", "drivers")


def test_ver_and_nor_deterministic_photo_mapping():
    """VER always resolves to max_verstappen.webp, NOR always resolves to lando_norris.webp."""
    assert get_driver_profile_image("VER") == "/drivers/max_verstappen.webp"
    assert get_driver_profile_image("NOR") == "/drivers/lando_norris.webp"
    assert get_driver_profile_image("HAM") == "/drivers/lewis_hamilton.webp"
    assert get_driver_profile_image("LEC") == "/drivers/charles_leclerc.webp"


def test_substitute_drivers_mapping():
    """Substitute drivers resolve to their distinct authentic photos."""
    expected_substitutes = {
        "BEA": "/drivers/oliver_bearman.webp",
        "LAW": "/drivers/liam_lawson.webp",
        "COL": "/drivers/franco_colapinto.webp",
        "DOO": "/drivers/jack_doohan.webp",
        "RIC": "/drivers/daniel_ricciardo.webp",
        "SAR": "/drivers/logan_sargeant.webp"
    }
    for tla, expected_img in expected_substitutes.items():
        assert get_driver_profile_image(tla) == expected_img, f"Failed mapping for substitute driver {tla}"


def test_fallback_driver_photo():
    """Unknown or missing driver abbreviation falls back gracefully."""
    fallback_img = get_driver_profile_image("UNKNOWN_XYZ")
    assert fallback_img == "/drivers/fallback_driver.webp"


def test_all_driver_assets_exist_on_disk():
    """Every mapped image file in DRIVER_SLUG_MAP and fallback must exist on disk in frontend/public/drivers/."""
    assert os.path.exists(os.path.join(PUBLIC_DRIVERS_DIR, "fallback_driver.webp")), "Fallback driver asset missing"
    
    for tla, slug in DRIVER_SLUG_MAP.items():
        img_path = os.path.join(PUBLIC_DRIVERS_DIR, f"{slug}.webp")
        assert os.path.exists(img_path), f"Driver portrait asset missing on disk for {tla}: {img_path}"
        assert os.path.getsize(img_path) > 200, f"Driver portrait asset is suspiciously small or corrupted: {img_path}"


def test_no_duplicate_slug_assignments():
    """Every driver abbreviation maps to a unique image file slug."""
    slugs = list(DRIVER_SLUG_MAP.values())
    assert len(slugs) == len(set(slugs)), "Duplicate image slug assigned in DRIVER_SLUG_MAP"


def test_api_session_drivers_contains_profile_image():
    """API /circuits/{circuit_id}/sessions/{session_id}/drivers returns profile_image with each driver."""
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res.status_code == 200
    data = res.json()
    assert "drivers" in data
    assert len(data["drivers"]) > 0

    for drv in data["drivers"]:
        assert "profile_image" in drv, f"Driver {drv.get('driver_id')} missing profile_image"
        assert drv["profile_image"].startswith("/drivers/"), f"Invalid profile_image path: {drv['profile_image']}"
        assert drv["profile_image"].endswith(".webp"), f"Non-WebP format returned: {drv['profile_image']}"


def test_driver_photo_not_dependent_on_race_position_or_array_index():
    """
    Ensures driver photos are strictly mapped by driver identity (abbreviation / ID)
    and do not change based on leaderboard position, array sorting, or lap progression.
    """
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/telemetry")
    assert res.status_code == 200
    telemetry = res.json()
    leaderboards = telemetry.get("leaderboards_by_lap", {})
    assert leaderboards, "Telemetry leaderboards_by_lap should not be empty"

    # Check multiple laps to verify photo remains invariant regardless of position changes
    for lap_str in ["1", "5", "10", str(telemetry.get("total_laps", 20))]:
        if lap_str in leaderboards:
            for row in leaderboards[lap_str]:
                tla = row["driver_id"]
                expected_photo = get_driver_profile_image(tla)
                assert row.get("profile_image") == expected_photo, (
                    f"Driver {tla} on lap {lap_str} (P{row['position']}) received wrong photo {row.get('profile_image')} instead of {expected_photo}"
                )


def test_session_change_updates_roster_photos():
    """Changing from Abu Dhabi to Albert Park to Jeddah returns appropriate driver photos for each session roster."""
    sessions = [
        ("abu_dhabi", "2024_abu_dhabi_R"),
        ("albert_park", "2024_albert_park_R"),
        ("jeddah", "2024_jeddah_R")
    ]
    for circuit_id, session_id in sessions:
        res = client.get(f"/circuits/{circuit_id}/sessions/{session_id}/drivers")
        assert res.status_code == 200
        drivers = res.json()["drivers"]
        for drv in drivers:
            tla = drv["driver_id"]
            expected = get_driver_profile_image(tla)
            assert drv["profile_image"] == expected, f"Photo mismatch for {tla} in session {session_id}"


def test_analytics_payload_contains_profile_image():
    """Bulk analytics endpoint /drivers/analytics includes profile_image for each driver."""
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/analytics")
    assert res.status_code == 200
    data = res.json()
    for drv_entry in data["drivers"]:
        driver_dict = drv_entry["driver"]
        tla = driver_dict["id"]
        assert "profile_image" in driver_dict
        assert driver_dict["profile_image"] == get_driver_profile_image(tla)
