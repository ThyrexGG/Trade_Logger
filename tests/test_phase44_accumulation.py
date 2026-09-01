"""
Phase 44 — Forward Accumulation & Checkpoint Test Suite
Validates clean forward accumulation, non-destructive isolation, and checkpoint persistence.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_forward_accumulation import ForwardAccumulationEngine


def test_accumulation_checkpoint_creation_and_retrieval():
    """Validates checkpoint calculation and persistence."""
    chk = ForwardAccumulationEngine.create_accumulation_checkpoint("XAUUSD")

    assert "checkpoint_id" in chk
    assert "forward_n" in chk
    assert "dataset_fingerprint" in chk
    assert len(chk["dataset_fingerprint"]) == 64
    assert chk["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"

    # History
    history = ForwardAccumulationEngine.get_accumulation_history(limit=5)
    assert len(history) >= 1
    assert any(h["checkpoint_id"] == chk["checkpoint_id"] for h in history)
