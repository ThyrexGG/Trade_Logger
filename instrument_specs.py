"""
Broker Instrument Specification Registry (Phase 12B)
Authoritative instrument specifications across asset classes (Forex, Metals, Indices, Crypto, Commodities).
Fail-closed on unknown or stale instrument specifications.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import symbol_mapping

@dataclass(frozen=True)
class InstrumentSpec:
    broker: str
    broker_symbol: str
    canonical_symbol: str
    asset_class: str      # FOREX, METALS, INDICES, CRYPTO, COMMODITIES
    digits: int           # Price decimal places
    point: float          # Smallest price increment
    tick_size: float      # Minimum price tick
    tick_value: float     # Cash value per tick for 1 standard lot
    contract_size: float  # Units per contract / lot
    min_qty: float        # Minimum lot size / order volume
    max_qty: float        # Maximum lot size / order volume
    qty_step: float       # Volume step increment
    currency: str         # Quote currency
    margin_factor: float  # Margin leverage ratio (e.g. 0.01 for 1:100 leverage)
    market_status: str    # OPEN, CLOSED, HALTED


# Standardized Base Catalog
DEFAULT_SPECS: Dict[str, Dict[str, Any]] = {
    # FOREX (Standard Lot = 100,000 units)
    "EURUSD": {
        "asset_class": "FOREX", "digits": 5, "point": 0.00001, "tick_size": 0.00001,
        "tick_value": 1.0, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.01, "market_status": "OPEN"
    },
    "GBPUSD": {
        "asset_class": "FOREX", "digits": 5, "point": 0.00001, "tick_size": 0.00001,
        "tick_value": 1.0, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.01, "market_status": "OPEN"
    },
    "USDJPY": {
        "asset_class": "FOREX", "digits": 3, "point": 0.001, "tick_size": 0.001,
        "tick_value": 0.65, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "JPY", "margin_factor": 0.01, "market_status": "OPEN"
    },
    "USDCHF": {
        "asset_class": "FOREX", "digits": 5, "point": 0.00001, "tick_size": 0.00001,
        "tick_value": 1.10, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "CHF", "margin_factor": 0.01, "market_status": "OPEN"
    },
    "AUDUSD": {
        "asset_class": "FOREX", "digits": 5, "point": 0.00001, "tick_size": 0.00001,
        "tick_value": 1.0, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.01, "market_status": "OPEN"
    },
    "USDCAD": {
        "asset_class": "FOREX", "digits": 5, "point": 0.00001, "tick_size": 0.00001,
        "tick_value": 0.74, "contract_size": 100000.0, "min_qty": 0.01, "max_qty": 100.0,
        "qty_step": 0.01, "currency": "CAD", "margin_factor": 0.01, "market_status": "OPEN"
    },
    
    # METALS (XAU = 100 oz per lot, XAG = 5000 oz per lot)
    "XAUUSD": {
        "asset_class": "METALS", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 1.0, "contract_size": 100.0, "min_qty": 0.01, "max_qty": 50.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.05, "market_status": "OPEN"
    },
    "XAGUSD": {
        "asset_class": "METALS", "digits": 3, "point": 0.001, "tick_size": 0.001,
        "tick_value": 5.0, "contract_size": 5000.0, "min_qty": 0.01, "max_qty": 20.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.10, "market_status": "OPEN"
    },
    
    # INDICES / CFDs (1 index contract per lot)
    "NAS100": {
        "asset_class": "INDICES", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 0.01, "contract_size": 1.0, "min_qty": 0.1, "max_qty": 500.0,
        "qty_step": 0.1, "currency": "USD", "margin_factor": 0.05, "market_status": "OPEN"
    },
    "US30": {
        "asset_class": "INDICES", "digits": 1, "point": 0.1, "tick_size": 0.1,
        "tick_value": 0.1, "contract_size": 1.0, "min_qty": 0.1, "max_qty": 500.0,
        "qty_step": 0.1, "currency": "USD", "margin_factor": 0.05, "market_status": "OPEN"
    },
    "SPX500": {
        "asset_class": "INDICES", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 0.01, "contract_size": 1.0, "min_qty": 0.1, "max_qty": 500.0,
        "qty_step": 0.1, "currency": "USD", "margin_factor": 0.05, "market_status": "OPEN"
    },
    "GER40": {
        "asset_class": "INDICES", "digits": 1, "point": 0.1, "tick_size": 0.1,
        "tick_value": 0.1, "contract_size": 1.0, "min_qty": 0.1, "max_qty": 200.0,
        "qty_step": 0.1, "currency": "EUR", "margin_factor": 0.05, "market_status": "OPEN"
    },
    
    # CRYPTO (1 coin per lot)
    "BTCUSD": {
        "asset_class": "CRYPTO", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 0.01, "contract_size": 1.0, "min_qty": 0.01, "max_qty": 10.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.20, "market_status": "OPEN"
    },
    "ETHUSD": {
        "asset_class": "CRYPTO", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 0.01, "contract_size": 1.0, "min_qty": 0.01, "max_qty": 50.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.20, "market_status": "OPEN"
    },
    
    # COMMODITIES (1,000 barrels per lot)
    "USOIL": {
        "asset_class": "COMMODITIES", "digits": 2, "point": 0.01, "tick_size": 0.01,
        "tick_value": 10.0, "contract_size": 1000.0, "min_qty": 0.01, "max_qty": 50.0,
        "qty_step": 0.01, "currency": "USD", "margin_factor": 0.10, "market_status": "OPEN"
    }
}


def get_instrument_spec(broker: str, symbol: str) -> Optional[InstrumentSpec]:
    """
    Returns authoritative InstrumentSpec for a given broker and symbol.
    Fails closed (returns None) if symbol or specification is unavailable.
    """
    canon = symbol_mapping.normalize_symbol(symbol)
    if not canon:
        return None
        
    brk = str(broker).upper().strip()
    brk_sym = symbol_mapping.get_broker_symbol(canon, brk)
    if not brk_sym:
        return None

    spec_data = DEFAULT_SPECS.get(canon)
    if not spec_data:
        return None

    return InstrumentSpec(
        broker=brk,
        broker_symbol=brk_sym,
        canonical_symbol=canon,
        asset_class=spec_data["asset_class"],
        digits=spec_data["digits"],
        point=spec_data["point"],
        tick_size=spec_data["tick_size"],
        tick_value=spec_data["tick_value"],
        contract_size=spec_data["contract_size"],
        min_qty=spec_data["min_qty"],
        max_qty=spec_data["max_qty"],
        qty_step=spec_data["qty_step"],
        currency=spec_data["currency"],
        margin_factor=spec_data["margin_factor"],
        market_status=spec_data["market_status"]
    )


def validate_order_volume(broker: str, symbol: str, volume: float) -> Tuple[bool, Optional[str]]:
    """
    Validates if volume respects min_qty, max_qty, and qty_step for the instrument.
    Returns (is_valid, error_reason).
    """
    spec = get_instrument_spec(broker, symbol)
    if not spec:
        return False, f"UNSUPPORTED_INSTRUMENT: No specification found for '{symbol}' on {broker}"

    if volume < spec.min_qty:
        return False, f"MIN_VOLUME_VIOLATION: Requested {volume} is below minimum {spec.min_qty} for {symbol}"
        
    if volume > spec.max_qty:
        return False, f"MAX_VOLUME_VIOLATION: Requested {volume} exceeds maximum {spec.max_qty} for {symbol}"

    # Verify step rounding
    remainder = round(volume % spec.qty_step, 6)
    if remainder != 0 and abs(remainder - spec.qty_step) > 1e-5:
        return False, f"VOLUME_STEP_VIOLATION: Volume {volume} does not align with step size {spec.qty_step}"

    return True, None
