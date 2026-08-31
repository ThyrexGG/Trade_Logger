"""
Structured Smart Money Concepts (SMC) & ICT Data Models (Phase 13)
Institutional-grade dataclasses representing Liquidity Pools, Fair Value Gaps (FVG/IFVG),
Order Blocks & Breaker Blocks, Dealing Ranges (Premium/Discount), and Market Structure Events (MSS/BOS/CHOCH).
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
import json
import uuid


@dataclass(frozen=True)
class LiquidityPool:
    """
    Represents a discrete institutional liquidity pool.
    Types: BSL_PDH, SSL_PDL, BSL_PWH, SSL_PWL, BSL_ASIAN, SSL_ASIAN,
           BSL_LONDON, SSL_LONDON, BSL_NY, SSL_NY, EQH, EQL, SWING_HIGH, SWING_LOW.
    """
    pool_id: str
    pool_type: str
    price: float
    timeframe: str
    created_at: str
    strength: float = 1.0
    is_swept: bool = False
    swept_at: Optional[str] = None
    sweep_bar_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FairValueGap:
    """
    Represents a 3-candle Fair Value Gap with ATR-based displacement validation.
    Supports standard mitigation and Inversion FVG (IFVG) state transitions.
    """
    fvg_id: str
    direction: str # "BULLISH" or "BEARISH"
    top: float
    bottom: float
    timeframe: str
    created_at: str
    bar_index: int
    displacement_atr_ratio: float = 1.5
    is_mitigated: bool = False
    mitigated_at: Optional[str] = None
    is_inversion: bool = False
    inversion_timestamp: Optional[str] = None

    @property
    def midpoint(self) -> float:
        """Consequent Encroachment (CE) / 50% equilibrium of the FVG."""
        return round((self.top + self.bottom) / 2.0, 5)

    @property
    def height_pips(self) -> float:
        return abs(self.top - self.bottom)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["midpoint"] = self.midpoint
        d["height_pips"] = self.height_pips
        return d


@dataclass(frozen=True)
class OrderBlock:
    """
    Represents an institutional Order Block (OB) or Breaker Block.
    """
    ob_id: str
    direction: str # "BULLISH" (Down-close candle before up move) or "BEARISH" (Up-close before down move)
    top: float
    bottom: float
    timeframe: str
    created_at: str
    bar_index: int
    displacement_atr_ratio: float = 1.5
    is_mitigated: bool = False
    mitigated_at: Optional[str] = None
    is_breaker: bool = False
    breaker_timestamp: Optional[str] = None
    mss_event_id: Optional[str] = None

    @property
    def mean_threshold(self) -> float:
        """Mean Threshold (MT) / 50% level of the Order Block."""
        return round((self.top + self.bottom) / 2.0, 5)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mean_threshold"] = self.mean_threshold
        return d


@dataclass(frozen=True)
class MarketStructureEvent:
    """
    Represents a structural shift in the market:
    - MSS: Market Structure Shift (Change of Character with displacement)
    - BOS: Break of Structure (Trend continuation through swing point)
    - CHOCH: Change of Character (Initial violation of minor swing)
    """
    event_id: str
    event_type: str # "MSS", "BOS", "CHOCH"
    direction: str # "BULLISH" or "BEARISH"
    price: float
    timeframe: str
    timestamp: str
    bar_index: int
    broken_swing_price: float
    displacement_atr_ratio: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DealingRange:
    """
    Represents the active Dealing Range for Fibonacci Premium vs Discount valuation.
    Equilibrium is the 50% level between high and low.
    """
    high: float
    low: float
    timeframe: str
    created_at: str

    @property
    def equilibrium(self) -> float:
        return round((self.high + self.low) / 2.0, 5)

    @property
    def premium_low(self) -> float:
        """Lower bound of premium zone (Equilibrium)."""
        return self.equilibrium

    @property
    def discount_high(self) -> float:
        """Upper bound of discount zone (Equilibrium)."""
        return self.equilibrium

    @property
    def range_size(self) -> float:
        return round(abs(self.high - self.low), 5)

    def get_zone(self, price: float) -> str:
        """Returns 'PREMIUM' (>50%), 'DISCOUNT' (<50%), or 'EQUILIBRIUM' (~50%)."""
        if self.range_size == 0:
            return "EQUILIBRIUM"
        pct = (price - self.low) / self.range_size
        if pct > 0.52:
            return "PREMIUM"
        elif pct < 0.48:
            return "DISCOUNT"
        else:
            return "EQUILIBRIUM"

    def get_fib_levels(self) -> Dict[str, float]:
        """Calculates standard ICT / SMC dealing range levels."""
        r = self.range_size
        return {
            "1.000_High": round(self.high, 5),
            "0.790_OTE": round(self.low + 0.790 * r, 5),
            "0.705_OTE_Mid": round(self.low + 0.705 * r, 5),
            "0.620_OTE": round(self.low + 0.620 * r, 5),
            "0.500_Equilibrium": self.equilibrium,
            "0.382_Discount": round(self.low + 0.382 * r, 5),
            "0.000_Low": round(self.low, 5)
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "high": self.high,
            "low": self.low,
            "equilibrium": self.equilibrium,
            "range_size": round(self.range_size, 5),
            "timeframe": self.timeframe,
            "created_at": self.created_at,
            "fib_levels": self.get_fib_levels()
        }


@dataclass
class SMCContext:
    """
    Unified multi-timeframe SMC Market Context snapshot containing all active institutional features.
    """
    symbol: str
    execution_timeframe: str
    structure_timeframe: str
    bias_timeframe: str
    timestamp: str
    current_price: float
    htf_bias: str # "BULLISH", "BEARISH", "NEUTRAL"
    dealing_range: Optional[DealingRange] = None
    active_liquidity_pools: List[LiquidityPool] = field(default_factory=list)
    recent_sweeps: List[LiquidityPool] = field(default_factory=list)
    active_fvgs: List[FairValueGap] = field(default_factory=list)
    active_order_blocks: List[OrderBlock] = field(default_factory=list)
    recent_structure_events: List[MarketStructureEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "execution_timeframe": self.execution_timeframe,
            "structure_timeframe": self.structure_timeframe,
            "bias_timeframe": self.bias_timeframe,
            "timestamp": self.timestamp,
            "current_price": self.current_price,
            "htf_bias": self.htf_bias,
            "dealing_range": self.dealing_range.to_dict() if self.dealing_range else None,
            "active_liquidity_pools": [p.to_dict() for p in self.active_liquidity_pools],
            "recent_sweeps": [s.to_dict() for s in self.recent_sweeps],
            "active_fvgs": [f.to_dict() for f in self.active_fvgs],
            "active_order_blocks": [o.to_dict() for o in self.active_order_blocks],
            "recent_structure_events": [e.to_dict() for e in self.recent_structure_events]
        }

    def to_ai_summary(self) -> str:
        """
        Formats a clean, factual summary suitable for direct injection into LLM prompts.
        Strictly mathematical and free of fabricated hallucination.
        """
        zone = self.dealing_range.get_zone(self.current_price) if self.dealing_range else "N/A"
        eq = self.dealing_range.equilibrium if self.dealing_range else "N/A"
        
        pools_txt = ", ".join([f"{p.pool_type}@{p.price:.5f}" for p in self.active_liquidity_pools[:4]]) or "None nearby"
        sweeps_txt = ", ".join([f"{s.pool_type}@{s.price:.5f}" for s in self.recent_sweeps[:2]]) or "No recent sweeps"
        fvgs_txt = ", ".join([f"{f.direction} FVG [{f.bottom:.5f}-{f.top:.5f}]" for f in self.active_fvgs[:3]]) or "No open FVGs"
        obs_txt = ", ".join([f"{o.direction} OB [{o.bottom:.5f}-{o.top:.5f}]" for o in self.active_order_blocks[:2]]) or "No active OBs"
        mss_txt = ", ".join([f"{e.event_type} {e.direction}@{e.price:.5f}" for e in self.recent_structure_events[:2]]) or "No recent shifts"

        return f"""--- SMC / ICT Market Context ---
Symbol: {self.symbol} | Exec TF: {self.execution_timeframe} | Struct TF: {self.structure_timeframe} | Bias TF: {self.bias_timeframe}
Current Price: {self.current_price:.5f} | HTF Directional Bias: {self.htf_bias}
Dealing Range: High={self.dealing_range.high if self.dealing_range else 'N/A'}, Low={self.dealing_range.low if self.dealing_range else 'N/A'} | Equilibrium={eq} | Current Zone={zone}
Active Liquidity Targets: {pools_txt}
Recent Liquidity Sweeps: {sweeps_txt}
Active Fair Value Gaps: {fvgs_txt}
Key Order Blocks: {obs_txt}
Recent Market Structure Shifts: {mss_txt}
---------------------------------"""
