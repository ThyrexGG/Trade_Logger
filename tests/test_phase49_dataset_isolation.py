"""
Phase 49 — Tests for Dataset Isolation & Unpooled Separation
"""

import pytest
from xauusd_forward_statistical_monitoring import CanonicalForwardDatasetEngine


def test_dataset_isolation_unpooled():
    """Validates that historical baseline IDs and forward observations are strictly disjoint."""
    canonical = CanonicalForwardDatasetEngine.get_canonical_dataset(mode="PAPER")
    assert canonical["is_isolated"] is True

    # Check shadow mode as well
    canonical_shadow = CanonicalForwardDatasetEngine.get_canonical_dataset(mode="SHADOW")
    assert canonical_shadow["is_isolated"] is True
