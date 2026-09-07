# -*- coding: utf-8 -*-
"""
Server-side Gemini client wrapper (Stage 15C; tool-calling added Phase W1).

The API key stays here — it is read from the environment (`GEMINI_API_KEY`, or
`GOOGLE_API_KEY`) and never returned to a caller. This wrapper has no knowledge
of TradeLogger execution / broker / order code and cannot reach it.

Tool-calling: `generate()` accepts an optional list of `google.genai` `Tool`
declarations plus a `tool_dispatch` callback. The model may *request* a tool;
this module runs the dispatch callback and feeds the result back. The dispatch
callback (see `api/ai_tools.py`) is a hard allowlist of read-only queries — this
module never decides what a tool does, only relays the request and the result.

If the key is not configured, `is_configured()` is False and the router returns
a graceful "assistant not configured" response — it never raises to the client.
"""
from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=False)

_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip() or "gemini-flash-lite-latest"
_TIMEOUT_SEC = float(os.getenv("GEMINI_TIMEOUT_SEC", "45") or "45")
# Default headroom: the gemini-3.x "flash" models are reasoning models and spend
# part of the budget on internal thinking before the answer — 800 was too tight
# and left them returning an empty text part.
_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "3000") or "3000")
# How many request/response round-trips of tool calls we allow before forcing a
# final text answer. Each read tool is cheap; this only bounds a pathological loop.
_MAX_TOOL_ROUNDS = int(os.getenv("GEMINI_MAX_TOOL_ROUNDS", "4") or "4")

# The SDK logs an INFO nag about "automatic function calling" on every
# generate_content call even when AFC is disabled — silence it.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)


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


def _classify(exc: Exception) -> GeminiError:
    msg = str(exc).lower()
    if "timeout" in msg or "deadline" in msg:
        return GeminiError("Gemini request timed out", kind="timeout")
    if ("rate" in msg and "limit" in msg) or "429" in msg or "quota" in msg or "resource_exhausted" in msg:
        return GeminiError("Gemini rate limit / quota exceeded", kind="rate_limit")
    return GeminiError(f"Gemini request failed: {type(exc).__name__}", kind="unavailable")


def _parts_text(resp: Any) -> str:
    """Pull the answer text out of a response, skipping reasoning ('thought') and
    function-call parts. `resp.text` alone returns None when the last turn is a
    tool request or a pure 'thought'."""
    try:
        txt = (resp.text or "").strip()
        if txt:
            return txt
    except Exception:
        pass
    try:
        parts = resp.candidates[0].content.parts or []
        return "".join(
            getattr(p, "text", "") or ""
            for p in parts
            if getattr(p, "text", "") and not getattr(p, "thought", False)
        ).strip()
    except Exception:
        return ""


def _accumulate_usage(dst: Dict[str, int], resp: Any) -> None:
    try:
        um = resp.usage_metadata
        dst["prompt_tokens"] += int(getattr(um, "prompt_token_count", 0) or 0)
        dst["output_tokens"] += int(getattr(um, "candidates_token_count", 0) or 0)
        dst["total_tokens"] += int(getattr(um, "total_token_count", 0) or 0)
    except Exception:
        pass


def generate(
    system_instruction: str,
    history: List[Dict[str, str]],
    context_block: str,
    *,
    tools: Optional[Sequence[Any]] = None,
    tool_dispatch: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    max_tool_rounds: int = _MAX_TOOL_ROUNDS,
) -> Tuple[str, Dict[str, Any]]:
    """
    Run one non-streaming generation. `history` is [{role: 'user'|'assistant', content}].
    The read-only TradeLogger context is injected as a leading user turn; the
    system instruction is fixed and cannot be overridden by history.

    If `tools` and `tool_dispatch` are supplied, the model may request a tool;
    each request is run through `tool_dispatch(name, args)` (which must be a
    read-only allowlist) and the result is fed back, up to `max_tool_rounds`
    round-trips, after which a final text answer is forced.

    Returns (reply_text, meta). `meta["tool_calls"]` is the per-call audit trail.
    Raises GeminiError on any provider problem.
    """
    if not is_configured():
        raise GeminiError("Gemini API key is not configured", kind="unavailable")

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # pragma: no cover - dependency present in requirements
        raise GeminiError(f"google-genai not importable: {exc}", kind="unavailable")

    tool_list = [t for t in (tools or []) if t is not None]
    use_tools = bool(tool_list and tool_dispatch is not None)

    try:
        client = genai.Client(
            api_key=_api_key(),
            http_options=types.HttpOptions(timeout=int(_TIMEOUT_SEC * 1000)),
        )

        config_kwargs: Dict[str, Any] = dict(
            system_instruction=system_instruction,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            temperature=0.2,
        )
        if use_tools:
            config_kwargs["tools"] = tool_list
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )
        config = types.GenerateContentConfig(**config_kwargs)

        contents: List[Any] = [
            types.Content(role="user", parts=[types.Part(text=context_block)]),
            types.Content(
                role="model",
                parts=[types.Part(text="Understood. I will use that snapshot as authoritative and will not perform any action.")],
            ),
        ]
        for turn in history:
            role = "model" if turn.get("role") == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=str(turn.get("content", "")))]))

        usage: Dict[str, int] = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        tool_calls: List[Dict[str, Any]] = []
        resp = None

        rounds = max_tool_rounds if use_tools else 0
        for round_idx in range(rounds + 1):
            last_round = round_idx == rounds
            call_config = config
            if use_tools and last_round:
                # Final pass: forbid further tool calls so we always end on text.
                call_config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                )
            resp = client.models.generate_content(model=_MODEL, contents=contents, config=call_config)
            _accumulate_usage(usage, resp)

            if not use_tools or last_round:
                break

            try:
                parts = resp.candidates[0].content.parts or []
            except Exception:
                parts = []
            fcs = [getattr(p, "function_call", None) for p in parts]
            fcs = [fc for fc in fcs if fc is not None]
            if not fcs:
                break

            contents.append(resp.candidates[0].content)
            for fc in fcs:
                name = getattr(fc, "name", "") or ""
                args = dict(getattr(fc, "args", None) or {})
                t0 = perf_counter()
                ok = True
                try:
                    result = tool_dispatch(name, args)  # type: ignore[misc]
                except Exception as exc:
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                    ok = False
                ms = int((perf_counter() - t0) * 1000)
                tool_calls.append({"tool": name, "args": args, "ms": ms, "ok": ok})
                payload = result if isinstance(result, dict) else {"result": result}
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(function_response=types.FunctionResponse(name=name, response=payload))],
                    )
                )
    except GeminiError:
        raise
    except Exception as exc:
        raise _classify(exc)

    text = _parts_text(resp)
    if not text:
        reason = None
        try:
            reason = getattr(resp.candidates[0], "finish_reason", None)
        except Exception:
            reason = None
        raise GeminiError(f"Gemini returned no usable text (finish_reason={reason})", kind="empty")

    meta: Dict[str, Any] = {
        "model": _MODEL,
        "finish_reason": "stop",
        "usage": {k: int(v) for k, v in usage.items()},
    }
    if tool_calls:
        meta["tool_calls"] = tool_calls
    return text, meta
