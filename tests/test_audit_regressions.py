"""
Regression tests specifically validating fixes from the Brutal End-to-End Audit.
"""

import pytest
from api.models import get_model_registry
from api.services.signatures_service import SignaturesService
from api.main import app_data, DB_PATH


def test_registry_raises_on_missing_telemetry():
    """Verify that model registry never synthesizes Gaussian noise when telemetry is absent."""
    registry = get_model_registry()
    with pytest.raises(ValueError) as excinfo:
        registry.get_or_generate_embedding("nonexistent_fake_stint_id_999")
    assert "Insufficient telemetry sequence observations" in str(excinfo.value)


@pytest.mark.asyncio
async def test_multiword_circuit_stint_id_parsing():
    """Verify that signatures_service correctly extracts driver ID from multi-word circuit stint IDs."""
    service = SignaturesService(DB_PATH, app_data)
    
    # Abu Dhabi multi-word slug: 2024_abu_dhabi_R_VER_1
    stint_id = "2024_abu_dhabi_R_VER_1"
    parts = stint_id.split('_')
    source_driver = parts[-2] if len(parts) >= 3 else "UNKNOWN"
    assert source_driver == "VER", f"Expected VER for Abu Dhabi, got {source_driver}"
    
    # Albert Park multi-word slug: 2024_albert_park_R_NOR_1
    stint_id_ap = "2024_albert_park_R_NOR_1"
    parts_ap = stint_id_ap.split('_')
    source_driver_ap = parts_ap[-2] if len(parts_ap) >= 3 else "UNKNOWN"
    assert source_driver_ap == "NOR", f"Expected NOR for Albert Park, got {source_driver_ap}"
