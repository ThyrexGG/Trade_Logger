# -*- coding: utf-8 -*-
"""
Phase 66 — provider registry & capability model.

Offline. Verifies discovery, capability declarations, unknown-provider handling
and that an unsupported capability is simply absent (never faked).
"""
from api.providers.registry import (
    CAPABILITY_CATEGORIES,
    Capability,
    MacroProviderRegistry,
)


def test_builtin_providers_are_registered():
    keys = set(MacroProviderRegistry.keys())
    assert {"fred", "cftc", "forecast", "sentiment"} <= keys


def test_unknown_provider_is_none_not_error():
    assert MacroProviderRegistry.get("does-not-exist") is None
    assert MacroProviderRegistry.capabilities_of("does-not-exist") == frozenset()


def test_fred_declares_observation_capabilities():
    caps = MacroProviderRegistry.capabilities_of("fred")
    assert Capability.OBSERVATIONS in caps
    assert Capability.REVISIONS in caps
    assert Capability.RELEASE_TIMESTAMPS in caps
    # FRED does NOT claim forecast / COT / sentiment — must be absent, not faked
    assert Capability.CONSENSUS_FORECAST not in caps
    assert Capability.COT_POSITIONING not in caps
    assert Capability.RETAIL_SENTIMENT not in caps


def test_cftc_declares_cot_only():
    caps = MacroProviderRegistry.capabilities_of("cftc")
    assert Capability.COT_POSITIONING in caps
    assert Capability.OBSERVATIONS not in caps
    assert Capability.CONSENSUS_FORECAST not in caps


def test_providers_for_capability():
    assert "cftc" in MacroProviderRegistry.providers_for(Capability.COT_POSITIONING)
    assert "forecast" in MacroProviderRegistry.providers_for(Capability.CONSENSUS_FORECAST)
    assert "fred" in MacroProviderRegistry.providers_for(Capability.OBSERVATIONS)
    assert MacroProviderRegistry.providers_for(Capability.PMI) == []


def test_discover_reports_configured_and_live(monkeypatch):
    monkeypatch.delenv("MACRO_COT_PROVIDER", raising=False)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    infos = {i.key: i for i in MacroProviderRegistry.discover()}
    # nothing configured by default
    assert infos["fred"].configured is False
    assert infos["cftc"].configured is False
    assert infos["forecast"].configured is False
    # health blocks never leak a key field
    for i in infos.values():
        blob = str(i.health).lower()
        assert "api_key" not in blob and "secret" not in blob and "token" not in blob


def test_cftc_configured_when_selected(monkeypatch):
    monkeypatch.setenv("MACRO_COT_PROVIDER", "cftc")
    infos = {i.key: i for i in MacroProviderRegistry.discover()}
    assert infos["cftc"].configured is True
    assert infos["cftc"].is_live is True


def test_capability_category_map_is_complete():
    # every capability that feeds a category is mapped
    for cap in (Capability.OBSERVATIONS, Capability.CONSENSUS_FORECAST,
                Capability.COT_POSITIONING, Capability.RETAIL_SENTIMENT):
        assert CAPABILITY_CATEGORIES.get(cap)
