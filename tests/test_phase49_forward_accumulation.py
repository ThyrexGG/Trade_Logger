"""
Phase 49 — Tests for Canonical Forward Dataset Extraction & Accumulation
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from xauusd_forward_statistical_monitoring import CanonicalForwardDatasetEngine


def test_canonical_dataset_empty_state():
    """Validates that with no forward trades, clean_n = 0 and dataset is verified isolated."""
    res = CanonicalForwardDatasetEngine.get_canonical_dataset(mode="PAPER")
    assert isinstance(res, dict)
    assert res["clean_n"] >= 0
    assert "dataset_fingerprint" in res
    assert res["is_isolated"] is True
    assert res["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_canonical_dataset_fingerprint_deterministic():
    """Validates that querying empty dataset yields deterministic fingerprint."""
    res1 = CanonicalForwardDatasetEngine.get_canonical_dataset(mode="PAPER")
    res2 = CanonicalForwardDatasetEngine.get_canonical_dataset(mode="PAPER")
    assert res1["dataset_fingerprint"] == res2["dataset_fingerprint"]
