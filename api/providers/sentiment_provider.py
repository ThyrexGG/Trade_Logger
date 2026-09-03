# -*- coding: utf-8 -*-
"""
Retail-sentiment / crowd-positioning provider contract (Phase 66).

Distinct from CFTC COT (institutional positioning). Retail sentiment means
broker client positioning (long % / short % / net) — e.g. OANDA order book,
IG / DailyFX client sentiment, FXCM SSI.

No live source is shipped:

  * OANDA's order-book / position-ratio endpoints require a funded v20 account.
  * IG / DailyFX client sentiment is gated behind an account and its terms
    restrict redistribution.
  * There is no free, authoritative, redistributable retail-positioning feed.

So the default is ``NullSentimentProvider`` and the Sentiment category stays
``INSUFFICIENT_EVIDENCE``. Sentiment is **never** manufactured from price action
or inferred from social-media activity.

No import of / path to execution_pipeline, broker_adapter, risk_gateway.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from api.providers.registry import Capability, sentiment_provider_key


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SentimentObservation:
    provider: str
    source: str
    instrument: str
    timestamp: str                       # provider's observation time (UTC ISO)
    long_pct: Optional[float] = None
    short_pct: Optional[float] = None
    net_pct: Optional[float] = None
    methodology: Optional[str] = None
    retrieved_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@runtime_checkable
class SentimentProvider(Protocol):
    KEY: str
    CAPABILITIES: frozenset
    name: str
    is_live: bool

    @property
    def configured(self) -> bool: ...

    def get_sentiment(self, *, as_of: Optional[datetime] = None) -> List[SentimentObservation]: ...

    def status(self) -> Dict[str, Any]: ...

    def hydrate(self) -> Dict[str, Any]: ...


class NullSentimentProvider:
    KEY = "none"
    CAPABILITIES = frozenset({Capability.RETAIL_SENTIMENT})
    name = "No sentiment provider"
    is_live = False

    @property
    def configured(self) -> bool:
        return False

    def get_sentiment(self, *, as_of: Optional[datetime] = None) -> List[SentimentObservation]:
        return []

    def status(self) -> Dict[str, Any]:
        return {
            "provider": "none",
            "provider_state": "NOT_CONFIGURED",
            "configured": False,
            "reason": "No retail-positioning source is configured. The Sentiment category "
                      "is INSUFFICIENT_EVIDENCE. Sentiment is never inferred from price or "
                      "social media.",
            "observations": 0,
        }

    def hydrate(self) -> Dict[str, Any]:
        return self.status()


_SENTIMENT_PROVIDERS = {
    "none": NullSentimentProvider,
}


def get_sentiment_provider() -> "SentimentProvider":
    key = sentiment_provider_key()
    factory = _SENTIMENT_PROVIDERS.get(key, NullSentimentProvider)
    return factory()
