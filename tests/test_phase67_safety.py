# -*- coding: utf-8 -*-
"""
Phase 67 — safety invariants for the unified evidence fusion layer.

Intelligence is context, never execution. The fusion engine, the model and the
router must not touch execution / broker / risk infrastructure, must not enable
automation, and must not change the frozen Strategy Contract.
"""
import hashlib
import os
import types

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_FROZEN_CONTRACT_HASH = "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
_FORBIDDEN_MODULES = {
    "execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
    "order_execution", "execution_config", "paper_simulator",
}
_PHASE67_MODULES = [
    "api.evidence_model",
    "api.evidence_fusion",
]


def test_strategy_contract_hash_unchanged():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
    assert digest == _FROZEN_CONTRACT_HASH


def test_live_automation_flags_unchanged_by_fusion():
    def _flags():
        h = client.get("/api/health").json()
        return h["automation_enabled"], h["live_broker_transmission"]

    assert _flags() == (False, "BLOCKED")
    client.get("/api/intelligence/asset/XAUUSD")
    client.get("/api/intelligence/asset/EURUSD?as_of=2026-08-01T00:00:00Z")
    assert _flags() == (False, "BLOCKED")


def test_phase67_modules_import_no_execution_module():
    for modname in _PHASE67_MODULES:
        mod = __import__(modname, fromlist=["_"])
        bound = {v.__name__ for v in vars(mod).values() if isinstance(v, types.ModuleType)}
        leaked = bound & _FORBIDDEN_MODULES
        assert not leaked, f"{modname} imports {leaked}"


def test_phase67_source_has_no_execution_reference():
    import api.evidence_fusion as f
    import api.evidence_model as m
    for src in (f, m):
        with open(src.__file__, encoding="utf-8") as fh:
            text = fh.read()
        for bad in _FORBIDDEN_MODULES:
            assert f"import {bad}" not in text
            assert f"from {bad} import" not in text
        assert "submit_order" not in text
        assert "transmit" not in text.lower() or "transmission" in text.lower()


def test_snapshot_declares_read_only_safety_barrier():
    j = client.get("/api/intelligence/asset/XAUUSD").json()
    assert j["safety_barrier"] == {
        "live_automation_enabled": False,
        "live_broker_transmission": "BLOCKED",
    }
    assert "never an execution signal" in j["disclaimer"].lower()


def test_no_secret_in_source():
    import api.evidence_fusion as f
    import api.evidence_model as m
    for mod in (f, m):
        with open(mod.__file__, encoding="utf-8") as fh:
            text = fh.read().lower()
        assert 'api_key = "' not in text
        assert 'secret = "' not in text
        assert 'token = "' not in text
