# -*- coding: utf-8 -*-
"""
FastAPI AI Assistant Router (Stage 15C).

A read-only analytical chat over an allowlisted TradeLogger context + Gemini.

**Security boundary.** This router imports exactly two internal modules —
`api.ai_context` (allowlisted read-only snapshot) and `api.gemini_client`
(server-side Gemini wrapper). It has NO import of / path to `execution_pipeline`,
`broker_adapter`, `risk_gateway`, order submission, position mutation or any
automation toggle, and it invokes none of them. `POST /api/ai/chat` generates
text only — the POST verb does not confer execution authority. Enforced by
`tests/test_stage15c_ai_assistant.py`.

The Gemini API key never leaves the server. If it is not configured the endpoint
returns `ok=false, error_kind="not_configured"` with HTTP 200 so the UI can show
a clean state — it never raises provider internals to the client.
"""
from datetime import datetime, timezone

from fastapi import APIRouter

from api.ai_context import (
    SYSTEM_INSTRUCTION,
    build_context,
    context_as_prompt_block,
)
from api.gemini_client import GeminiError, generate, is_configured, model_name
from api.schemas import AIChatRequest, AIChatResponse, AIStatusResponse

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/status", response_model=AIStatusResponse)
def ai_status() -> AIStatusResponse:
    """Whether the assistant is configured (no secret is ever returned)."""
    return AIStatusResponse(
        configured=is_configured(),
        model=model_name() if is_configured() else None,
        timestamp=_now(),
    )


@router.post("/chat", response_model=AIChatResponse)
def ai_chat(req: AIChatRequest) -> AIChatResponse:
    """
    Generate one analytical reply grounded in a read-only TradeLogger snapshot.
    Never executes, submits, modifies, cancels or transmits an order; has no
    tool that could. Provider failures come back as `ok=false` with an
    `error_kind`, not as a 5xx or a stack trace.
    """
    if not is_configured():
        return AIChatResponse(
            ok=False,
            error="The AI assistant is not configured on this server (no GEMINI_API_KEY).",
            error_kind="not_configured",
            timestamp=_now(),
        )

    ctx = build_context()
    history = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        reply, meta = generate(SYSTEM_INSTRUCTION, history, context_as_prompt_block(ctx))
    except GeminiError as exc:
        kind_map = {
            "unavailable": "provider_unavailable",
            "timeout": "timeout",
            "rate_limit": "rate_limit",
            "empty": "empty",
            "bad_response": "provider_unavailable",
        }
        return AIChatResponse(
            ok=False,
            error=str(exc),
            error_kind=kind_map.get(exc.kind, "provider_unavailable"),
            model=model_name(),
            context_sections_used=ctx["available_sections"],
            context_sections_unavailable=ctx["unavailable_sections"],
            timestamp=_now(),
        )

    return AIChatResponse(
        ok=True,
        reply=reply,
        model=str(meta.get("model", model_name())),
        context_sections_used=ctx["available_sections"],
        context_sections_unavailable=ctx["unavailable_sections"],
        timestamp=_now(),
    )
