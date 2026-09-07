"""
Tests for Offline Precomputation and KV Cache Prewarming.
"""

import pytest
from api.jobs.precompute import run_precompute


@pytest.mark.asyncio
async def test_offline_precompute_execution():
    summary = await run_precompute()
    
    assert summary["circuits"] == 13
    assert summary["stints"] >= 6
    assert summary["evaluated_laps"] >= 943
    assert summary["embeddings_generated"] >= 6
    assert summary["attributions_cached"] >= 6
    assert summary["maps_cached"] == 13
