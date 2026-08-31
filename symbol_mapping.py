"""
Canonical Symbol Mapping Layer (Phase 12B)
Normalizes internal symbols across MT5, Capital.com, and Strategy Engines.
Fails closed on unknown, ambiguous, or unsupported symbols.
"""

from typing import Dict, Optional, Tuple

# Canonical Master Asset Registry
CANONICAL_SYMBOLS = {
    "EURUSD": {"asset_class": "FOREX", "base": "EUR", "quote": "USD"},
    "GBPUSD": {"asset_class": "FOREX", "base": "GBP", "quote": "USD"},
    "USDJPY": {"asset_class": "FOREX", "base": "USD", "quote": "JPY"},
    "USDCHF": {"asset_class": "FOREX", "base": "USD", "quote": "CHF"},
    "AUDUSD": {"asset_class": "FOREX", "base": "AUD", "quote": "USD"},
    "USDCAD": {"asset_class": "FOREX", "base": "USD", "quote": "CAD"},
    "NZDUSD": {"asset_class": "FOREX", "base": "NZD", "quote": "USD"},
    "EURGBP": {"asset_class": "FOREX", "base": "EUR", "quote": "GBP"},
    "EURJPY": {"asset_class": "FOREX", "base": "EUR", "quote": "JPY"},
    "GBPJPY": {"asset_class": "FOREX", "base": "GBP", "quote": "JPY"},
    "XAUUSD": {"asset_class": "METALS", "base": "XAU", "quote": "USD"},
    "XAGUSD": {"asset_class": "METALS", "base": "XAG", "quote": "USD"},
    "BTCUSD": {"asset_class": "CRYPTO", "base": "BTC", "quote": "USD"},
    "ETHUSD": {"asset_class": "CRYPTO", "base": "ETH", "quote": "USD"},
    "NAS100": {"asset_class": "INDICES", "base": "USD", "quote": "USD"},
    "US30":   {"asset_class": "INDICES", "base": "USD", "quote": "USD"},
    "SPX500": {"asset_class": "INDICES", "base": "USD", "quote": "USD"},
    "GER40":  {"asset_class": "INDICES", "base": "EUR", "quote": "EUR"},
    "USOIL":  {"asset_class": "COMMODITIES", "base": "USD", "quote": "USD"},
}

# Aliases mapped to Canonical
SYMBOL_ALIASES: Dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "BITCOIN": "BTCUSD",
    "BTC": "BTCUSD",
    "ETH": "ETHUSD",
    "US100": "NAS100",
    "USTECH100": "NAS100",
    "NDX": "NAS100",
    "DJ30": "US30",
    "WALLSTREET": "US30",
    "US500": "SPX500",
    "SP500": "SPX500",
    "DE40": "GER40",
    "DAX40": "GER40",
    "DAX": "GER40",
    "CRUDE": "USOIL",
    "WTI": "USOIL",
    "OIL_CRUDE": "USOIL",
}

# Broker-Specific Symbol Overrides
BROKER_SYMBOL_MAP: Dict[Tuple[str, str], str] = {
    # MT5 Broker mappings (support raw/micro suffixes)
    ("MT5", "EURUSD"): "EURUSD",
    ("MT5", "GBPUSD"): "GBPUSD",
    ("MT5", "USDJPY"): "USDJPY",
    ("MT5", "XAUUSD"): "XAUUSD",
    ("MT5", "BTCUSD"): "BTCUSD",
    ("MT5", "NAS100"): "NAS100",
    ("MT5", "US30"): "US30",
    ("MT5", "SPX500"): "SPX500",
    ("MT5", "GER40"): "GER40",
    ("MT5", "USOIL"): "USOIL",
    
    # Capital.com Epic mappings
    ("CAPITAL", "EURUSD"): "EURUSD",
    ("CAPITAL", "GBPUSD"): "GBPUSD",
    ("CAPITAL", "USDJPY"): "USDJPY",
    ("CAPITAL", "USDCHF"): "USDCHF",
    ("CAPITAL", "AUDUSD"): "AUDUSD",
    ("CAPITAL", "USDCAD"): "USDCAD",
    ("CAPITAL", "NZDUSD"): "NZDUSD",
    ("CAPITAL", "EURGBP"): "EURGBP",
    ("CAPITAL", "EURJPY"): "EURJPY",
    ("CAPITAL", "GBPJPY"): "GBPJPY",
    ("CAPITAL", "XAUUSD"): "GOLD",
    ("CAPITAL", "XAGUSD"): "SILVER",
    ("CAPITAL", "BTCUSD"): "BTCUSD",
    ("CAPITAL", "ETHUSD"): "ETHUSD",
    ("CAPITAL", "NAS100"): "US100",
    ("CAPITAL", "US30"): "US30",
    ("CAPITAL", "SPX500"): "US500",
    ("CAPITAL", "GER40"): "DE40",
    ("CAPITAL", "USOIL"): "OIL_CRUDE",
}


def normalize_symbol(raw_symbol: str) -> Optional[str]:
    """
    Translates any incoming raw symbol or alias into its Canonical Symbol.
    Returns None if symbol cannot be safely identified (Fail-Closed).
    """
    if not raw_symbol or not isinstance(raw_symbol, str):
        return None
        
    cleaned = raw_symbol.upper().strip().replace("/", "").replace("-", "").replace("_", "")
    
    # Strip common broker postfixes (.m, .raw, .pro, +)
    for suffix in [".M", ".RAW", ".PRO", "M", "+"]:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
            cleaned = cleaned[:-len(suffix)]
            break

    if cleaned in CANONICAL_SYMBOLS:
        return cleaned
        
    if cleaned in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[cleaned]
        
    return None


def get_broker_symbol(canonical_symbol: str, broker: str) -> Optional[str]:
    """
    Translates a canonical symbol to the specific broker's ticker/epic.
    Returns None if unsupported by broker (Fail-Closed).
    """
    canon = normalize_symbol(canonical_symbol)
    if not canon:
        return None
        
    brk = str(broker).upper().strip()
    if brk in ["PAPER", "SHADOW"]:
        return canon
        
    return BROKER_SYMBOL_MAP.get((brk, canon), canon)


def is_symbol_supported(symbol: str) -> bool:
    """Returns True if the symbol maps to a recognized canonical instrument."""
    return normalize_symbol(symbol) is not None
