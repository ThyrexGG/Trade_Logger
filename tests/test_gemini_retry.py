# -*- coding: utf-8 -*-
"""Gemini answers a transient 5xx (google.genai ServerError) fairly often; the client retries those, and only those."""
import pytest

from api import gemini_client


class ServerError(Exception):
    """Same class name as google.genai.errors.ServerError — the retry keys on the name."""


class _Models:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class _Client:
    def __init__(self, outcomes):
        self.models = _Models(outcomes)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(gemini_client, "sleep", lambda s: None)
    monkeypatch.setattr(gemini_client, "_SERVER_RETRIES", 2)


def test_retries_server_errors_then_succeeds():
    c = _Client([ServerError("503"), ServerError("503"), "ok"])
    assert gemini_client._generate_with_retry(c, model="m") == "ok"
    assert c.models.calls == 3


def test_gives_up_after_the_retry_budget():
    c = _Client([ServerError("503")] * 3)
    with pytest.raises(ServerError):
        gemini_client._generate_with_retry(c, model="m")
    assert c.models.calls == 3


def test_other_errors_are_not_retried():
    c = _Client([RuntimeError("bad key"), "ok"])
    with pytest.raises(RuntimeError):
        gemini_client._generate_with_retry(c, model="m")
    assert c.models.calls == 1
