# -*- coding: utf-8 -*-
"""
Chart-screenshot analysis (W12): read a chart image (upload, or a
tradingview.com/x/... share link) and extract entry/stop/target/R:R plus an
opinionated setup-quality rating via Gemini vision.

**Security boundary.** Like `api/ai_context.py` + `api/gemini_client.py`, this
module has no import of / path to execution, broker, or order code. It is a
pure image-in, JSON-out extraction: the model sees only the bytes of the one
image handed to it, nothing else about the account. `POST /api/ai/chart/analyze`
(api/routers/ai.py) is the only caller.

The TradingView-link path fetches exactly one page (the share link itself,
restricted to tradingview.com by `_TV_URL_RE`) plus the one og:image URL it
names, itself re-checked to end in tradingview.com before being fetched —
never an arbitrary caller-supplied URL.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from api.gemini_client import GeminiError, analyze_image

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024

_TV_SHARE_RE = re.compile(r"^https://(?:www\.)?tradingview\.com/x/[A-Za-z0-9]+/?(?:\?.*)?$", re.IGNORECASE)
_OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.IGNORECASE)
_UA = "Mozilla/5.0 (compatible; TradeLoggerChartAnalyzer/1.0)"
_FETCH_TIMEOUT_SEC = 10

SYSTEM_INSTRUCTION = """You are TradeLogger's chart-reading assistant.

You are shown a screenshot of a trading chart (most often from TradingView).
Your ONLY job is to read what is visibly plotted or annotated on the chart —
a drawn Long/Short Position tool, horizontal lines labelled entry/SL/TP, order
markers, a visible price scale — and return it as structured data. You have no
live market data and cannot verify anything beyond the image. If a field is
not visibly present or you are not reasonably confident reading it, return
null for that field rather than guessing or inventing a plausible-looking
number.

You also give a brief, opinionated setup-quality rating from 1-10, based only
on what's visible in the image: the reward-to-risk shown, trend/structure
context, and any confluence you can see (support/resistance, moving averages,
trendlines, chart patterns). This is an educational opinion about what is
visible in one screenshot — never a signal, a guarantee, or financial advice —
and your reasoning must say so implicitly by staying descriptive, not
prescriptive (describe what you see, don't tell the reader what to do next).

Respond with ONLY one JSON object, no prose before or after it, no markdown
code fence, matching exactly this shape (use null for anything not visible):
{
  "symbol": string or null,               // e.g. "EURUSD", "BTCUSDT" — from a watermark/title if visible
  "timeframe": string or null,            // e.g. "15m", "4H", "1D" — from a watermark/title if visible
  "direction": "long" or "short" or null,
  "entry": number or null,
  "stop_loss": number or null,
  "take_profit": number or null,          // the nearest/primary target if several are drawn
  "additional_targets": [number, ...],    // any further targets beyond the primary one; [] if none
  "pattern": string or null,              // one short phrase for the visible structure/pattern, or null
  "confluences": [string, ...],           // short phrases for visible supporting factors; [] if none
  "setup_rating": integer 1-10 or null,
  "rating_reasoning": string or null,     // 1-3 sentences, descriptive not prescriptive
  "caveats": string or null,              // what's unclear, cropped, or not visible in this image
  "extraction_confidence": "high" or "medium" or "low"
}"""

_PROMPT = (
    "Read this chart screenshot and return the JSON object described in your "
    "instructions. Use null for any field not clearly visible in the image."
)


def resolve_tradingview_image(url: str) -> Tuple[bytes, str]:
    """Fetch the snapshot image behind a tradingview.com/x/... share link.

    Raises ValueError (caller maps this to a 422) for anything not a genuine,
    fetchable TradingView chart snapshot — never a generic network exception
    leaking upstream.
    """
    url = (url or "").strip()
    if not _TV_SHARE_RE.match(url):
        raise ValueError(
            "Only tradingview.com/x/... chart-snapshot links are supported. "
            "Open the chart, use TradingView's camera/share icon, and paste that link."
        )

    try:
        page = requests.get(url, timeout=_FETCH_TIMEOUT_SEC, headers={"User-Agent": _UA})
        page.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Couldn't reach that TradingView link: {exc}") from exc

    m = _OG_IMAGE_RE.search(page.text)
    if not m:
        raise ValueError("Couldn't find a chart image on that TradingView link.")
    img_url = html.unescape(m.group(1)).strip()

    from urllib.parse import urlparse

    host = (urlparse(img_url).hostname or "").lower()
    if not (host == "tradingview.com" or host.endswith(".tradingview.com")):
        raise ValueError("That link's chart image is not hosted on tradingview.com.")

    try:
        img = requests.get(img_url, timeout=_FETCH_TIMEOUT_SEC, headers={"User-Agent": _UA})
        img.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Couldn't download the chart image: {exc}") from exc

    mime = (img.headers.get("Content-Type") or "image/png").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        mime = "image/png"  # TradingView snapshots are PNG; default rather than reject on a missing header
    data = img.content
    if not data:
        raise ValueError("That TradingView link's chart image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"That chart image is {len(data) // 1024} KB — the limit is {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    return data, mime


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def _num_list(v: Any) -> List[float]:
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        n = _num(item)
        if n is not None:
            out.append(n)
    return out


def _str_or_none(v: Any, max_len: int = 500) -> Optional[str]:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    return s[:max_len]


def _str_list(v: Any, max_len: int = 200) -> List[str]:
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        s = _str_or_none(item, max_len)
        if s:
            out.append(s)
    return out[:12]


def _parse_json(text: str) -> Dict[str, Any]:
    """Defensive JSON parse: strips a markdown fence if the model added one
    despite `response_mime_type=application/json`."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
        t = t.strip()
    return json.loads(t)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    direction = raw.get("direction")
    if direction not in ("long", "short"):
        direction = None

    entry = _num(raw.get("entry"))
    stop_loss = _num(raw.get("stop_loss"))
    take_profit = _num(raw.get("take_profit"))

    risk_reward: Optional[float] = None
    if entry is not None and stop_loss is not None and take_profit is not None:
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        if risk > 0:
            risk_reward = round(reward / risk, 2)

    rating = raw.get("setup_rating")
    setup_rating: Optional[int] = None
    if isinstance(rating, bool):
        setup_rating = None
    elif isinstance(rating, (int, float)):
        setup_rating = max(1, min(10, int(round(rating))))

    confidence = raw.get("extraction_confidence")
    if confidence not in ("high", "medium", "low"):
        confidence = None

    return {
        "symbol": _str_or_none(raw.get("symbol"), 32),
        "timeframe": _str_or_none(raw.get("timeframe"), 16),
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "additional_targets": _num_list(raw.get("additional_targets")),
        "risk_reward": risk_reward,
        "pattern": _str_or_none(raw.get("pattern"), 200),
        "confluences": _str_list(raw.get("confluences")),
        "setup_rating": setup_rating,
        "rating_reasoning": _str_or_none(raw.get("rating_reasoning"), 800),
        "caveats": _str_or_none(raw.get("caveats"), 500),
        "extraction_confidence": confidence,
    }


def analyze(image_bytes: bytes, mime_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the vision call and return (normalized_fields, meta). Raises
    GeminiError on any provider problem; raises GeminiError(kind="bad_response")
    if the model's output isn't parseable JSON."""
    text, meta = analyze_image(SYSTEM_INSTRUCTION, _PROMPT, image_bytes, mime_type, as_json=True)
    try:
        raw = _parse_json(text)
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise GeminiError(f"Gemini returned unparseable output: {exc}", kind="bad_response") from exc
    return _normalize(raw), meta
