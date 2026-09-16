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
import base64
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.ai_context import (
    SYSTEM_INSTRUCTION,
    build_context,
    context_as_prompt_block,
)
from api.gemini_client import GeminiError, generate, is_configured, model_name
from api.schemas import AIChatRequest, AIChatResponse, AIStatusResponse, ChartAnalysisResponse

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])

_ERROR_KIND_MAP = {
    "unavailable": "provider_unavailable",
    "timeout": "timeout",
    "rate_limit": "rate_limit",
    "empty": "empty",
    "bad_response": "bad_response",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/status", response_model=AIStatusResponse)
def ai_status() -> AIStatusResponse:
    """Whether the assistant is configured (no secret is ever returned)."""
    from api import ai_usage

    return AIStatusResponse(
        configured=is_configured(),
        model=model_name() if is_configured() else None,
        usage=ai_usage.snapshot(),
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

    from api import ai_usage
    import tenant

    wait = ai_usage.rate_limited_for(tenant.current_user_id())
    if wait is not None:
        return AIChatResponse(
            ok=False,
            error=f"Too many AI requests — try again in about {max(1, wait // 60)} minute(s).",
            error_kind="rate_limit",
            timestamp=_now(),
        )
    ai_usage.record_request(tenant.current_user_id())

    ctx = build_context()
    history = [{"role": m.role, "content": m.content} for m in req.messages]

    from api import ai_tools

    try:
        tool_decls = ai_tools.gemini_tool_declarations()
    except Exception:
        tool_decls = None

    try:
        reply, meta = generate(
            SYSTEM_INSTRUCTION,
            history,
            context_as_prompt_block(ctx),
            tools=tool_decls,
            tool_dispatch=ai_tools.dispatch,
        )
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

    from api import ai_usage

    turn_usage = meta.get("usage") or {}
    ai_usage.record(int(turn_usage.get("total_tokens", 0) or 0))

    return AIChatResponse(
        ok=True,
        reply=reply,
        model=str(meta.get("model", model_name())),
        context_sections_used=ctx["available_sections"],
        context_sections_unavailable=ctx["unavailable_sections"],
        turn_usage=turn_usage or None,
        usage=ai_usage.snapshot(),
        tool_calls=meta.get("tool_calls") or None,
        timestamp=_now(),
    )


@router.post("/chart/analyze", response_model=ChartAnalysisResponse)
async def chart_analyze(
    file: Optional[UploadFile] = File(default=None),
    tradingview_url: Optional[str] = Form(default=None),
) -> ChartAnalysisResponse:
    """
    Read one chart screenshot — an uploaded image, or a tradingview.com/x/...
    share link — and extract entry/stop/target/R:R plus an AI setup-quality
    opinion. Pure image-to-JSON extraction: no execution path, no account or
    market-data lookup; Gemini sees only the bytes of this one image.
    """
    if not is_configured():
        return ChartAnalysisResponse(
            ok=False,
            error="The AI assistant is not configured on this server (no GEMINI_API_KEY).",
            error_kind="not_configured",
            timestamp=_now(),
        )

    from api import ai_usage
    import tenant

    wait = ai_usage.rate_limited_for(tenant.current_user_id())
    if wait is not None:
        return ChartAnalysisResponse(
            ok=False,
            error=f"Too many AI requests — try again in about {max(1, wait // 60)} minute(s).",
            error_kind="rate_limit",
            timestamp=_now(),
        )
    ai_usage.record_request(tenant.current_user_id())

    if bool(file) == bool(tradingview_url):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of: an uploaded image, or a tradingview_url.",
        )

    from api import chart_analysis

    if file is not None:
        mime = (file.content_type or "").lower().split(";")[0].strip()
        if mime not in chart_analysis.ALLOWED_MIME:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image type '{mime}'. Allowed: PNG, JPEG, WebP.",
            )
        data = await file.read()
        if not data:
            raise HTTPException(status_code=422, detail="Empty file")
        if len(data) > chart_analysis.MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image is {len(data) // 1024} KB — the limit is "
                f"{chart_analysis.MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            )
    else:
        try:
            data, mime = chart_analysis.resolve_tradingview_image(tradingview_url or "")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    try:
        fields, meta = chart_analysis.analyze(data, mime)
    except GeminiError as exc:
        return ChartAnalysisResponse(
            ok=False,
            error=str(exc),
            error_kind=_ERROR_KIND_MAP.get(exc.kind, "provider_unavailable"),
            model=model_name(),
            timestamp=_now(),
        )

    from api import ai_usage

    turn_usage = meta.get("usage") or {}
    ai_usage.record(int(turn_usage.get("total_tokens", 0) or 0))

    return ChartAnalysisResponse(
        ok=True,
        model=str(meta.get("model", model_name())),
        image_base64=base64.b64encode(data).decode("ascii"),
        image_mime=mime,
        turn_usage=turn_usage or None,
        usage=ai_usage.snapshot(),
        timestamp=_now(),
        **fields,
    )
