# -*- coding: utf-8 -*-
"""
Tests for W12 — chart-screenshot analysis (POST /api/ai/chart/analyze).

Same execution-isolation posture as Stage 15C: this is a pure image-to-JSON
extraction over Gemini vision, with no import of / path to execution_pipeline,
broker_adapter, risk_gateway, order submission or position mutation.
"""
import io
import types

import pytest
from fastapi.testclient import TestClient

from api import chart_analysis
from api.main import app

client = TestClient(app)

_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415408d763f8ffff3f0005fe02fea1e6b8a50000000049454e44ae426082"
)


# --- request validation --------------------------------------------------

def test_rejects_neither_file_nor_url():
    assert client.post("/api/ai/chart/analyze", data={}).status_code == 422


def test_rejects_both_file_and_url():
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    data = {"tradingview_url": "https://www.tradingview.com/x/abc123/"}
    assert client.post("/api/ai/chart/analyze", files=files, data=data).status_code == 422


def test_rejects_unsupported_mime():
    files = {"file": ("chart.gif", b"GIF89a", "image/gif")}
    assert client.post("/api/ai/chart/analyze", files=files).status_code == 415


def test_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(chart_analysis, "MAX_IMAGE_BYTES", 10)
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    r = client.post("/api/ai/chart/analyze", files=files)
    assert r.status_code == 413


def test_rejects_empty_file():
    files = {"file": ("chart.png", b"", "image/png")}
    assert client.post("/api/ai/chart/analyze", files=files).status_code == 422


def test_analyze_is_post_only():
    assert client.get("/api/ai/chart/analyze").status_code == 405


# --- TradingView link validation (no network call for a bad link) --------

@pytest.mark.parametrize("bad_url", [
    "https://evil.example.com/x/abc123/",
    "https://tradingview.com.evil.com/x/abc123/",
    "http://www.tradingview.com/x/abc123/",  # not https
    "https://www.tradingview.com/chart/abc123/",  # not a /x/ share link
    "not a url",
    "",
])
def test_tradingview_url_validation_rejects_non_share_links(bad_url):
    with pytest.raises(ValueError):
        chart_analysis.resolve_tradingview_image(bad_url)


def test_tradingview_bad_link_surfaces_as_422():
    r = client.post("/api/ai/chart/analyze", data={"tradingview_url": "https://evil.example.com/x/abc123/"})
    assert r.status_code == 422


# --- not configured -> graceful 200 --------------------------------------

def test_not_configured_is_graceful_200():
    from api import gemini_client
    if gemini_client.is_configured():
        pytest.skip("a real key is configured in this environment")
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    r = client.post("/api/ai/chart/analyze", files=files)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False
    assert d["error_kind"] == "not_configured"
    assert d["live_broker_transmission"] == "BLOCKED"


# --- stubbed provider: success + failure paths ---------------------------

@pytest.fixture()
def stub_configured(monkeypatch):
    monkeypatch.setattr("api.routers.ai.is_configured", lambda: True)
    monkeypatch.setattr("api.routers.ai.model_name", lambda: "stub-model")


def test_success_path_returns_normalized_fields(stub_configured, monkeypatch):
    def fake_analyze(image_bytes, mime_type):
        assert image_bytes == _PNG_BYTES
        assert mime_type == "image/png"
        fields = {
            "symbol": "EURUSD", "timeframe": "15m", "direction": "long",
            "entry": 1.0850, "stop_loss": 1.0820, "take_profit": 1.0920,
            "additional_targets": [1.0950], "risk_reward": 2.33,
            "pattern": "ascending triangle", "confluences": ["50 EMA support"],
            "setup_rating": 7, "rating_reasoning": "Clean structure, decent R:R.",
            "caveats": None, "extraction_confidence": "high",
        }
        return fields, {"model": "stub-model", "usage": {"prompt_tokens": 10, "output_tokens": 5, "total_tokens": 15}}

    monkeypatch.setattr("api.chart_analysis.analyze", fake_analyze)
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    r = client.post("/api/ai/chart/analyze", files=files)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["symbol"] == "EURUSD"
    assert d["direction"] == "long"
    assert d["risk_reward"] == 2.33
    assert d["setup_rating"] == 7
    assert d["read_only"] is True
    assert d["live_broker_transmission"] == "BLOCKED"
    assert "not financial advice" in d["disclaimer"].lower()
    # the analyzed image is echoed back so the client can attach it to a
    # journal trade/entry afterward, regardless of upload vs. TradingView-link
    import base64 as _b64
    assert d["image_mime"] == "image/png"
    assert _b64.b64decode(d["image_base64"]) == _PNG_BYTES


def test_provider_failure_is_graceful(stub_configured, monkeypatch):
    from api.gemini_client import GeminiError

    def boom(image_bytes, mime_type):
        raise GeminiError("simulated outage", kind="timeout")

    monkeypatch.setattr("api.chart_analysis.analyze", boom)
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    r = client.post("/api/ai/chart/analyze", files=files)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and d["error_kind"] == "timeout"
    assert "Traceback" not in (d["error"] or "")


def test_unparseable_model_output_is_graceful(stub_configured, monkeypatch):
    def fake_analyze_image(system_instruction, prompt, image_bytes, mime_type, **kwargs):
        return "not json at all", {"model": "stub-model", "usage": {}}

    monkeypatch.setattr("api.chart_analysis.analyze_image", fake_analyze_image)
    files = {"file": ("chart.png", _PNG_BYTES, "image/png")}
    r = client.post("/api/ai/chart/analyze", files=files)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and d["error_kind"] == "bad_response"


# --- normalization unit tests --------------------------------------------

def test_normalize_computes_risk_reward_server_side():
    raw = {"entry": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1150, "direction": "long"}
    out = chart_analysis._normalize(raw)
    assert out["risk_reward"] == 3.0  # reward .0150 / risk .0050


def test_normalize_drops_invalid_direction_and_rating():
    raw = {"direction": "sideways", "setup_rating": 99}
    out = chart_analysis._normalize(raw)
    assert out["direction"] is None
    assert out["setup_rating"] == 10  # clamped


def test_normalize_defaults_missing_fields_to_none_or_empty():
    out = chart_analysis._normalize({})
    assert out["symbol"] is None
    assert out["additional_targets"] == []
    assert out["confluences"] == []
    assert out["risk_reward"] is None


# --- execution isolation (the important part) -----------------------------

def test_chart_analysis_binds_no_execution_symbol():
    forbidden_names = {
        "execution_pipeline", "broker_adapter", "risk_gateway", "submit_order",
        "get_broker_adapter", "CanonicalExecutionRequest", "execution_recorder",
    }
    for name, value in vars(chart_analysis).items():
        assert name not in forbidden_names, f"chart_analysis binds {name}"
        if isinstance(value, types.ModuleType):
            top = value.__name__.split(".")[0]
            assert top not in forbidden_names, f"chart_analysis imports {value.__name__}"
