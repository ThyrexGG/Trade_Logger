# -*- coding: utf-8 -*-
"""
Server-side Gemini client wrapper (Stage 15C).

The API key stays here — it is read from the environment (`GEMINI_API_KEY`, or
`GOOGLE_API_KEY`) and never returned to a caller. This wrapper has no knowledge
of TradeLogger execution / broker / order code and cannot reach it.

If the key is not configured, `is_configured()` is False and the router returns
a graceful "assistant not configured" response — it never raises to the client.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=False)

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip() or "gemini-1.5-flash"
_TIMEOUT_SEC = float(os.getenv("GEMINI_TIMEOUT_SEC", "30") or "30")
_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "800") or "800")


def _api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def is_configured() -> bool:
    return bool(_api_key())


def model_name() -> str:
    return _MODEL


class GeminiError(Exception):
    """Provider-side failure. `kind` is one of: unavailable, timeout, rate_limit, empty, bad_response."""

    def __init__(self, message: str, kind: str = "unavailable"):
        super().__init__(message)
        self.kind = kind


def generate(system_instruction: str, history: List[Dict[str, str]], context_block: str) -> Tuple[str, Dict[str, Any]]:
    """
    Run one non-streaming generation. `history` is [{role: 'user'|'assistant', content}].
    The read-only TradeLogger context is injected as a leading user turn; the
    system instruction is fixed and cannot be overridden by history.
    Returns (reply_text, meta). Raises GeminiError on any provider problem.
    """
    if not is_configured():
        raise GeminiError("Gemini API key is not configured", kind="unavailable")

    try:
        import google.generativeai as genai
    except Exception as exc:  # pragma: no cover - dependency present in requirements
        raise GeminiError(f"google-generativeai not importable: {exc}", kind="unavailable")

    try:
        genai.configure(api_key=_api_key())
        model = genai.GenerativeModel(_MODEL, system_instruction=system_instruction)

        contents: List[Dict[str, Any]] = [
            {"role": "user", "parts": [context_block]},
            {"role": "model", "parts": ["Understood. I will use that snapshot as authoritative and will not perform any action."]},
        ]
        for turn in history:
            role = "model" if turn.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [str(turn.get("content", ""))]})

        resp = model.generate_content(
            contents,
            generation_config={"max_output_tokens": _MAX_OUTPUT_TOKENS, "temperature": 0.2},
            request_options={"timeout": _TIMEOUT_SEC},
        )
    except GeminiError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg or "deadline" in msg:
            raise GeminiError("Gemini request timed out", kind="timeout")
        if "rate" in msg and "limit" in msg or "429" in msg or "quota" in msg or "resource_exhausted" in msg:
            raise GeminiError("Gemini rate limit / quota exceeded", kind="rate_limit")
        raise GeminiError(f"Gemini request failed: {type(exc).__name__}", kind="unavailable")

    text = ""
    try:
        text = (resp.text or "").strip()
    except Exception:
        # blocked / no candidates
        pass
    if not text:
        reason = None
        try:
            reason = getattr(resp.candidates[0], "finish_reason", None)
        except Exception:
            reason = None
        raise GeminiError(f"Gemini returned no usable text (finish_reason={reason})", kind="empty")

    return text, {"model": _MODEL, "finish_reason": "stop"}
