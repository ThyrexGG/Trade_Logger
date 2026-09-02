"""
Central Risk Gateway (Phase 12A)
Mandatory execution risk filter evaluating per-trade risk, broker-reconciled account state,
portfolio open risk, directional correlation, and market data health.
Deterministic and strictly fail-closed.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
import database
import market_data
import account_state
import symbol_mapping
import instrument_specs

# --- Stage 3.5C: bounded caches for the calculation-only risk preview path ---
# These are consumed ONLY by calculate_pre_trade_risk_preview(). The authoritative
# execution gate evaluate_trade_risk() deliberately does not use them and keeps
# reading live state uncached.
_PREVIEW_OPEN_POSITIONS_TTL_SEC = 2.0        # reuses database._DB_CACHE["open_positions_None"]
_PREVIEW_CORRELATION_TTL_SEC = 300.0         # correlation_matrix is near-static (periodic batch refresh)

# key = tuple(sorted((sym_a, sym_b))) -> (correlation_value, epoch_timestamp)
_CORRELATION_CACHE: Dict[Tuple[str, str], Tuple[float, float]] = {}


def clear_correlation_cache() -> None:
    """Deterministically clears the preview-path correlation memo (used by tests/benchmarks)."""
    _CORRELATION_CACHE.clear()


def get_account_state(broker: str):
    return account_state.get_account_state(broker)


def get_contract_size(symbol: str) -> float:
    """Returns standardized contract size per instrument class."""
    sym = str(symbol).upper().strip()
    if "XAU" in sym or "GOLD" in sym:
        return 100.0  # 100 oz per lot
    elif "BTC" in sym or "ETH" in sym or "CRYPTO" in sym:
        return 1.0    # 1 coin per contract
    elif "US30" in sym or "NAS100" in sym or "SPX500" in sym or "GER40" in sym:
        return 1.0    # Index contracts
    elif "USOIL" in sym or "UKOIL" in sym:
        return 1000.0 # 1000 barrels per lot
    else:
        return 100000.0  # Standard FX lot = 100,000 units


# ---------------------------------------------------------------------------
# Currency-aware position sizing helpers
# ---------------------------------------------------------------------------
# The account currency is USD. A price move on an FX contract produces P/L
# denominated in the pair's QUOTE currency, which must be converted to USD
# before it can be compared against a USD risk budget. These helpers reuse the
# authoritative canonical registry (symbol_mapping.CANONICAL_SYMBOLS) and broker
# specs (instrument_specs.DEFAULT_SPECS) instead of hardcoding per-symbol values.

def _symbol_currencies(symbol: str) -> Tuple[str, Optional[str], Optional[str]]:
    """(canonical_symbol, base_ccy, quote_ccy). Falls back to slicing a 6-char FX code."""
    raw = str(symbol).upper().strip()
    canon = symbol_mapping.normalize_symbol(raw) or raw
    meta = symbol_mapping.CANONICAL_SYMBOLS.get(canon)
    if meta:
        return canon, meta.get("base"), meta.get("quote")
    spec = instrument_specs.DEFAULT_SPECS.get(canon, {})
    quote = spec.get("currency")
    letters = "".join(ch for ch in canon if ch.isalpha())
    if len(letters) == 6:
        return canon, letters[:3], (quote or letters[3:])
    return canon, None, quote


def _symbol_spec(symbol: str) -> Dict[str, Any]:
    raw = str(symbol).upper().strip()
    canon = symbol_mapping.normalize_symbol(raw) or raw
    return instrument_specs.DEFAULT_SPECS.get(canon, {})


def quote_ccy_to_usd_factor(symbol: str, reference_price: float) -> Tuple[float, Optional[str]]:
    """
    Multiplier that converts a P/L amount denominated in the pair's QUOTE
    currency into USD (the account currency). Returns (factor, warning_or_None).

      quote == USD           -> 1.0            (EURUSD, GBPUSD, XAUUSD, USD-priced indices)
      base  == USD (USD/XXX) -> 1.0 / price    (USDJPY, USDCHF, USDCAD): 1 quote unit = 1/price USD
      cross (neither is USD) -> static spec estimate (tick_value / tick_size / contract_size),
                                else 1.0 with a warning (no live cross-rate in the calc-only path)
    """
    canon, base, quote = _symbol_currencies(symbol)
    if not quote or quote == "USD":
        return 1.0, None
    if base == "USD":
        if reference_price and float(reference_price) > 0:
            return 1.0 / float(reference_price), None
        return 1.0, f"{canon}: reference price unavailable for {quote}->USD conversion."
    # Cross pair — no direct USD leg in this pair.
    spec = _symbol_spec(symbol)
    cs = float(spec.get("contract_size", 0.0) or 0.0)
    tv = float(spec.get("tick_value", 0.0) or 0.0)
    ts = float(spec.get("tick_size", 0.0) or 0.0)
    if cs > 0 and tv > 0 and ts > 0:
        return (tv / ts) / cs, (
            f"{canon}: {quote}->USD uses a static spec estimate; live cross-rate "
            f"is not available in the calculation-only path."
        )
    return 1.0, (
        f"{canon}: {quote}->USD rate unavailable; risk is shown in {quote} terms "
        f"without currency conversion."
    )


def position_risk_usd(symbol: str, price_distance: float, lots: float, reference_price: float) -> Tuple[float, Optional[str]]:
    """
    Worst-case P/L in USD for `lots` over `price_distance` price units, using the
    authoritative contract size and quote->USD conversion. Long/short symmetric
    (the caller passes abs(entry - stop)).
    """
    spec = _symbol_spec(symbol)
    c_size = float(spec.get("contract_size") or 0.0) or get_contract_size(symbol)
    factor, warn = quote_ccy_to_usd_factor(symbol, reference_price)
    return abs(float(price_distance)) * float(lots) * c_size * factor, warn


def position_notional_usd(symbol: str, lots: float, reference_price: float) -> float:
    """USD notional controlled by `lots` — base currency exposure converted to USD."""
    spec = _symbol_spec(symbol)
    c_size = float(spec.get("contract_size") or 0.0) or get_contract_size(symbol)
    canon, base, quote = _symbol_currencies(symbol)
    units = float(lots) * c_size  # units of the base currency / instrument
    if base == "USD":
        return units  # USD is the base -> notional already in USD
    if quote == "USD" or not quote:
        return units * float(reference_price)  # base priced directly in USD
    # Cross: approximate via quote-notional then convert quote -> USD.
    factor, _ = quote_ccy_to_usd_factor(symbol, reference_price)
    return units * float(reference_price) * factor


def margin_factor_for(symbol: str, fallback_leverage: float = 30.0) -> float:
    """Broker margin factor from instrument_specs (e.g. 0.01 = 1:100), else 1/leverage."""
    spec = _symbol_spec(symbol)
    mf = spec.get("margin_factor")
    try:
        mf = float(mf)
        if mf > 0:
            return mf
    except (TypeError, ValueError):
        pass
    lev = float(fallback_leverage) if fallback_leverage else 30.0
    return 1.0 / max(1.0, lev)


def get_pair_correlation(sym_a: str, sym_b: str, ttl_sec: float = 0.0) -> float:
    """Looks up correlation between two assets from correlation_matrix or returns baseline.

    ttl_sec > 0 opts into a bounded in-memory memo (Stage 3.5C). Default 0.0 keeps the
    original uncached behaviour for the authoritative execution gate.
    """
    if sym_a == sym_b:
        return 1.0
    if ttl_sec > 0:
        key = tuple(sorted((sym_a, sym_b)))
        hit = _CORRELATION_CACHE.get(key)
        if hit is not None and (time.time() - hit[1]) < ttl_sec:
            return hit[0]
    val = _lookup_pair_correlation(sym_a, sym_b)
    if ttl_sec > 0:
        _CORRELATION_CACHE[tuple(sorted((sym_a, sym_b)))] = (val, time.time())
    return val


def _lookup_pair_correlation(sym_a: str, sym_b: str) -> float:
    """Authoritative correlation lookup: correlation_matrix table, then baseline fallback."""
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        q = """
            SELECT correlation FROM correlation_matrix 
            WHERE (symbol_1 = %s AND symbol_2 = %s) OR (symbol_1 = %s AND symbol_2 = %s)
            ORDER BY updated_at DESC LIMIT 1
        """ if database.is_postgres() else """
            SELECT correlation FROM correlation_matrix 
            WHERE (symbol_1 = ? AND symbol_2 = ?) OR (symbol_1 = ? AND symbol_2 = ?)
            ORDER BY updated_at DESC LIMIT 1
        """
        cursor.execute(q, (sym_a, sym_b, sym_b, sym_a))
        row = cursor.fetchone()
        conn.close()
        if row:
            return float(row[0])
    except Exception:
        pass
        
    # Baseline macro-correlations fallback
    known_corrs = {
        ("EURUSD", "GBPUSD"): 0.84,
        ("EURUSD", "USDCHF"): -0.92,
        ("EURUSD", "USDJPY"): -0.45,
        ("GBPUSD", "USDJPY"): -0.38,
        ("XAUUSD", "EURUSD"): 0.65,
        ("NAS100", "SPX500"): 0.94,
        ("US30", "SPX500"): 0.89
    }
    for (a, b), val in known_corrs.items():
        if (sym_a == a and sym_b == b) or (sym_a == b and sym_b == a):
            return val
    return 0.0


def evaluate_trade_risk(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates comprehensive risk for a proposed signal.
    Returns:
    {
        "approved": bool,
        "risk_score": float,
        "reasons": list,
        "warnings": list,
        "account_state": dict,
        "portfolio_state": dict,
        "trade_risk": dict
    }
    """
    symbol = str(signal.get("symbol", "")).upper().strip()
    direction = str(signal.get("side", signal.get("direction", ""))).upper().strip()
    volume = float(signal.get("requested_quantity", signal.get("volume", 0.0)))
    entry = float(signal.get("requested_entry", signal.get("entry_price", 0.0)))
    sl = float(signal.get("stop_loss", signal.get("sl", 0.0))) if signal.get("stop_loss") or signal.get("sl") else None
    tp = float(signal.get("take_profit", signal.get("tp", 0.0))) if signal.get("take_profit") or signal.get("tp") else None
    broker = str(signal.get("broker", "CAPITAL")).upper().strip()
    mode = str(signal.get("mode", "PAPER")).upper().strip()

    res = {
        "approved": False,
        "risk_score": 0.0,
        "reasons": [],
        "warnings": [],
        "account_state": {},
        "portfolio_state": {},
        "trade_risk": {}
    }

    # 1. EMERGENCY KILL SWITCH CHECK
    kill_switch = database.get_setting("GLOBAL_KILL_SWITCH", "FALSE").upper()
    sys_state = database.get_setting("SYSTEM_STATE", "PAPER").upper()
    if kill_switch == "TRUE" or sys_state == "EMERGENCY HALT":
        res["reasons"].append("EMERGENCY_HALT_ACTIVE: System kill switch is engaged. All trading blocked.")
        return res

    # 2. BASIC VALIDATION & LOT SIZING
    if not symbol:
        res["reasons"].append("INVALID_SYMBOL: Symbol cannot be empty.")
        return res
    if direction not in ["BUY", "SELL"]:
        res["reasons"].append(f"INVALID_DIRECTION: Direction '{direction}' must be 'BUY' or 'SELL'.")
        return res
    if volume <= 0:
        res["reasons"].append(f"INVALID_VOLUME: Volume ({volume}) must be greater than zero.")
        return res
    if volume < 0.01:
        res["reasons"].append(f"MIN_LOT_VIOLATION: Volume ({volume}) is below broker minimum (0.01).")
        return res

    # 3. MARKET DATA HEALTH GATE
    try:
        health = market_data.get_market_health(symbol, "1m")
        if mode in ["LIVE", "LIVE_MICRO"] and health.get("status") in ["STALE", "DISCONNECTED"]:
            res["reasons"].append(f"MARKET_DATA_UNHEALTHY: Market feed for {symbol} is {health.get('status')}.")
            return res
        elif health.get("status") in ["STALE", "DISCONNECTED"]:
            res["warnings"].append(f"Market health check degraded/offline ({health.get('status')}).")
    except Exception as e:
        res["warnings"].append(f"Market health check bypassed (offline simulation): {e}")

    # 4. STOP LOSS & TAKE PROFIT GEOMETRY VALIDITY
    if entry > 0 and sl is not None:
        if direction == "BUY" and sl >= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: BUY Stop Loss ({sl}) must be strictly below Entry ({entry}).")
            return res
        if direction == "SELL" and sl <= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: SELL Stop Loss ({sl}) must be strictly above Entry ({entry}).")
            return res

    if entry > 0 and tp is not None:
        if direction == "BUY" and tp <= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: BUY Take Profit ({tp}) must be strictly above Entry ({entry}).")
            return res
        if direction == "SELL" and tp >= entry:
            res["reasons"].append(f"GEOMETRY_ERROR: SELL Take Profit ({tp}) must be strictly below Entry ({entry}).")
            return res

    # 5. BROKER-RECONCILED ACCOUNT STATE (FAIL-CLOSED)
    account_data = None
    if mode in ["LIVE", "LIVE_MICRO"]:
        state_fetch = get_account_state(broker)
        if not state_fetch or state_fetch.get("status") not in ["success", "HEALTHY"]:
            err_details = state_fetch.get("message") or state_fetch.get("error_message") if state_fetch else "No response"
            res["reasons"].append(f"UNAVAILABLE_ACCOUNT_STATE: Unable to fetch authoritative broker account state for {broker}: {err_details}")
            return res
        account_data = state_fetch
    else:
        # Paper / Shadow local fallback
        balances = database.get_account_balances()
        account_data = balances.get("PAPER", list(balances.values())[0] if balances else {"balance": 10000.0, "equity": 10000.0, "floating_pnl": 0.0})

    res["account_state"] = account_data
    balance = float(account_data.get("balance", 10000.0))
    equity = float(account_data.get("equity", balance))
    floating_pnl = float(account_data.get("floating_pnl", 0.0))

    if balance <= 0:
        res["reasons"].append("INSUFFICIENT_EQUITY: Account balance is zero or negative.")
        return res

    # 6. PER-TRADE RISK CALCULATION
    # Currency-aware: P/L is denominated in the pair's quote currency and
    # converted to USD via the canonical base/quote registry (shared with the
    # pre-trade preview). Behaviour is unchanged for USD-base pairs (USDJPY /
    # USDCHF / USDCAD -> divide by entry) and USD-quote pairs (EURUSD, XAUUSD ->
    # no conversion); only non-USD crosses are now converted instead of being
    # mis-counted as already-USD.
    _spec = _symbol_spec(symbol)
    contract_size = float(_spec.get("contract_size") or 0.0) or get_contract_size(symbol)
    trade_risk_usd = 0.0
    trade_risk_pct = 0.0
    if sl is not None and entry > 0:
        dist = abs(entry - sl)
        trade_risk_usd, _conv_warn = position_risk_usd(symbol, dist, volume, entry)
        if _conv_warn:
            res["warnings"].append(_conv_warn)
        trade_risk_pct = (trade_risk_usd / balance) * 100.0

    res["trade_risk"] = {
        "risk_amount_usd": round(trade_risk_usd, 2),
        "risk_pct": round(trade_risk_pct, 2),
        "contract_size": contract_size
    }

    max_trade_risk_pct = float(database.get_setting("MAX_TRADE_RISK_PCT", "5.0"))
    if trade_risk_pct > max_trade_risk_pct:
        res["reasons"].append(f"TRADE_RISK_EXCEEDED: Trade risk ({trade_risk_pct:.2f}%) exceeds maximum limit ({max_trade_risk_pct:.2f}%).")
        return res

    # 7. TOTAL PORTFOLIO OPEN RISK & EXPOSURE
    open_positions_df = database.get_open_positions()
    total_open_risk_usd = 0.0
    symbol_positions_count = 0
    directional_long_count = 0
    directional_short_count = 0

    if not open_positions_df.empty:
        for _, pos in open_positions_df.iterrows():
            pos_sym = str(pos["symbol"]).upper()
            pos_dir = str(pos["direction"]).upper()
            pos_vol = float(pos.get("volume", 0.0))
            pos_entry = float(pos.get("entry_price", 0.0))
            pos_sl = float(pos.get("sl", 0.0))

            if pos_sym == symbol:
                symbol_positions_count += 1
            if "BUY" in pos_dir or "LONG" in pos_dir:
                directional_long_count += 1
            else:
                directional_short_count += 1

            if pos_sl > 0 and pos_entry > 0:
                p_csize = get_contract_size(pos_sym)
                p_dist = abs(pos_entry - pos_sl)
                total_open_risk_usd += (p_dist * pos_vol * p_csize)

    # Check Max Symbol Exposure (Limit 2 positions per asset)
    max_symbol_exposure = int(database.get_setting("MAX_SYMBOL_EXPOSURE", "2"))
    if symbol_positions_count >= max_symbol_exposure:
        res["reasons"].append(f"SYMBOL_EXPOSURE_LIMIT: Already holding {symbol_positions_count} open positions for {symbol} (Max: {max_symbol_exposure}).")
        return res

    # Check Total Open Risk (including in-flight concurrency risk reservations)
    import execution_pipeline
    reserved_risk_pct = execution_pipeline.get_reserved_portfolio_risk_pct()
    total_open_risk_pct = (total_open_risk_usd / balance) * 100.0
    projected_total_risk_pct = total_open_risk_pct + reserved_risk_pct + trade_risk_pct

    res["portfolio_state"] = {
        "open_positions_count": len(open_positions_df),
        "total_open_risk_usd": round(total_open_risk_usd, 2),
        "total_open_risk_pct": round(total_open_risk_pct, 2),
        "reserved_in_flight_risk_pct": round(reserved_risk_pct, 2),
        "projected_total_risk_pct": round(projected_total_risk_pct, 2)
    }

    max_total_risk_pct = float(database.get_setting("MAX_TOTAL_RISK_PCT", "15.0"))
    if projected_total_risk_pct > max_total_risk_pct:
        res["reasons"].append(f"TOTAL_RISK_LIMIT: Projected total open risk ({projected_total_risk_pct:.2f}% [Open: {total_open_risk_pct:.2f}%, In-Flight: {reserved_risk_pct:.2f}%, New: {trade_risk_pct:.2f}%]) exceeds maximum limit ({max_total_risk_pct:.2f}%).")
        return res

    # 8. DIRECTION-AWARE CORRELATION RISK
    max_correlated_positions = int(database.get_setting("MAX_CORRELATED_EXPOSURE", "2"))
    if not open_positions_df.empty:
        for _, pos in open_positions_df.iterrows():
            pos_sym = str(pos["symbol"]).upper()
            pos_dir = str(pos["direction"]).upper()
            if pos_sym == symbol:
                continue
                
            corr = get_pair_correlation(symbol, pos_sym)
            if abs(corr) >= 0.80:
                same_direction = (direction == "BUY" and ("BUY" in pos_dir or "LONG" in pos_dir)) or \
                                 (direction == "SELL" and ("SELL" in pos_dir or "SHORT" in pos_dir))
                
                # Positive correlation in same direction multiplies directional exposure
                if corr > 0 and same_direction:
                    res["reasons"].append(
                        f"CORRELATION_RISK: New {direction} on {symbol} would accumulate excessive directional risk with open {pos_dir} on {pos_sym} (Correlation: {corr:.2f})."
                    )
                    return res
                # Negative correlation in opposite direction also multiplies risk
                elif corr < 0 and not same_direction:
                    res["reasons"].append(
                        f"INVERSE_CORRELATION_RISK: New {direction} on {symbol} with open {pos_dir} on {pos_sym} (Correlation: {corr:.2f}) doubles exposure."
                    )
                    return res
                else:
                    res["warnings"].append(f"Correlated pair ({pos_sym}) open, but acting in hedging orientation (Corr: {corr:.2f}).")

    # 9. DAILY LOSS PROTECTION (REALIZED + BROKER FLOATING PNL)
    daily_realized_pnl = float(account_data.get("realized_daily_pnl", 0.0))
    total_daily_pnl = daily_realized_pnl + floating_pnl
    
    # Calculate daily loss threshold (default: 3% of balance)
    max_daily_loss_pct = float(database.get_setting("MAX_DAILY_LOSS_PCT", "3.0"))
    max_daily_loss_usd = -(balance * (max_daily_loss_pct / 100.0))
    
    if total_daily_pnl < max_daily_loss_usd:
        res["reasons"].append(
            f"DAILY_LOSS_BREACH: Combined daily loss (${abs(total_daily_pnl):,.2f} [Realized: ${daily_realized_pnl:,.2f}, Floating: ${floating_pnl:,.2f}]) exceeds maximum limit of ${abs(max_daily_loss_usd):,.2f} ({max_daily_loss_pct}%)."
        )
        return res

    # ALL GATES PASSED
    res["approved"] = True
    res["risk_score"] = round(trade_risk_pct / max_trade_risk_pct, 4) if max_trade_risk_pct > 0 else 0.0
    return res


def calculate_pre_trade_risk_preview(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    take_profit_1: Optional[float] = None,
    take_profit_2: Optional[float] = None,
    requested_risk_pct: float = 1.0,
    account_balance: float = 10000.0,
    leverage: float = 30.0
) -> Dict[str, Any]:
    """
    Calculates comprehensive pre-trade risk preview metrics for traders:
    - Recommended position size (lots) aligned to 0.01 lot steps
    - Absolute worst-case loss ($ and %) at stop loss
    - Projected profits ($ and %) at TP1 and TP2
    - Risk to Reward (R:R) ratio
    - Estimated margin requirement
    - Correlation warnings against existing open portfolio
    """
    sym = str(symbol).upper().strip()
    direction = str(side).upper().strip()
    entry = float(entry_price) if entry_price else 0.0
    sl = float(stop_loss) if stop_loss else 0.0
    tp1 = float(take_profit_1) if take_profit_1 else 0.0
    tp2 = float(take_profit_2) if take_profit_2 else 0.0
    bal = max(100.0, float(account_balance))
    risk_pct = max(0.01, float(requested_risk_pct))

    preview = {
        "symbol": sym,
        "side": direction,
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "account_balance": bal,
        "target_risk_usd": round(bal * (risk_pct / 100.0), 2),
        "calculated_lot_size": 0.01,
        "actual_risk_usd": 0.0,
        "actual_risk_pct": 0.0,
        "reward_tp1_usd": 0.0,
        "reward_tp1_pct": 0.0,
        "reward_tp2_usd": 0.0,
        "reward_tp2_pct": 0.0,
        "risk_reward_ratio": "N/A",
        "estimated_margin_usd": 0.0,
        "is_valid": True,
        "warnings": [],
        "errors": []
    }

    if entry <= 0:
        preview["is_valid"] = False
        preview["errors"].append("Invalid Entry Price: must be greater than 0.")
        return preview

    if sl <= 0:
        preview["is_valid"] = False
        preview["errors"].append("Stop Loss is required for institutional risk sizing.")
        return preview

    sl_dist = abs(entry - sl)
    if sl_dist <= 0:
        preview["is_valid"] = False
        preview["errors"].append("Stop Loss cannot equal Entry Price.")
        return preview

    # Geometry Validation
    if direction in ["BUY", "LONG"] and sl >= entry:
        preview["is_valid"] = False
        preview["errors"].append(f"BUY Stop Loss ({sl:.5f}) must be strictly below Entry ({entry:.5f}).")
    elif direction in ["SELL", "SHORT"] and sl <= entry:
        preview["is_valid"] = False
        preview["errors"].append(f"SELL Stop Loss ({sl:.5f}) must be strictly above Entry ({entry:.5f}).")

    spec = _symbol_spec(sym)
    c_size = float(spec.get("contract_size") or 0.0) or get_contract_size(sym)
    # Rounding step kept at the historical 0.01 lot; min/max clamp uses the
    # broker spec where available (this fix is scoped to currency conversion,
    # not lot-step granularity).
    lot_step = 0.01
    min_qty = float(spec.get("min_qty") or 0.0) or 0.01
    max_qty = float(spec.get("max_qty") or 0.0) or 1_000_000.0
    target_risk_usd = bal * (risk_pct / 100.0)

    # Currency-aware position sizing. P/L on an FX contract is denominated in the
    # pair's QUOTE currency and converted to USD (the account currency) via the
    # canonical base/quote registry — e.g. USDJPY divides by the USDJPY price,
    # EURUSD needs no conversion. Conversion is referenced at the entry price
    # (the single price known at sizing time, consistent with the execution gate).
    conv_factor, conv_warn = quote_ccy_to_usd_factor(sym, entry)
    if conv_warn:
        preview["warnings"].append(conv_warn)

    usd_risk_per_lot = sl_dist * c_size * conv_factor
    # Lots = Target Risk (USD) / worst-case USD loss per lot
    raw_lots = (target_risk_usd / usd_risk_per_lot) if usd_risk_per_lot > 0 else min_qty
    lots = round(round(raw_lots / lot_step) * lot_step, 2)  # snap to nearest 0.01 lot
    lots = min(max(lots, min_qty), max_qty)

    actual_risk_usd = sl_dist * lots * c_size * conv_factor
    actual_risk_pct = (actual_risk_usd / bal) * 100.0

    preview["calculated_lot_size"] = lots
    preview["actual_risk_usd"] = round(actual_risk_usd, 2)
    preview["actual_risk_pct"] = round(actual_risk_pct, 2)

    # Reward & R:R Calculations (same quote->USD conversion as the risk leg)
    if tp1 > 0:
        tp1_dist = abs(tp1 - entry)
        tp1_usd = tp1_dist * lots * c_size * conv_factor
        preview["reward_tp1_usd"] = round(tp1_usd, 2)
        preview["reward_tp1_pct"] = round((tp1_usd / bal) * 100.0, 2)
        rr = tp1_dist / sl_dist if sl_dist > 0 else 0.0
        preview["risk_reward_ratio"] = f"1:{rr:.2f}"

    if tp2 > 0:
        tp2_dist = abs(tp2 - entry)
        tp2_usd = tp2_dist * lots * c_size * conv_factor
        preview["reward_tp2_usd"] = round(tp2_usd, 2)
        preview["reward_tp2_pct"] = round((tp2_usd / bal) * 100.0, 2)

    # Estimated Margin — USD notional * broker margin factor (from instrument_specs).
    # For USDJPY the base currency is USD, so notional is lots*contract_size USD
    # (NOT entry*lots*contract_size, which would be a JPY figure).
    notional_usd = position_notional_usd(sym, lots, entry)
    margin_req = notional_usd * margin_factor_for(sym, fallback_leverage=leverage)
    preview["estimated_margin_usd"] = round(margin_req, 2)

    # Check Portfolio Correlation Warnings
    # Stage 3.5C: this block is advisory-only (produces warnings[], affects no number).
    # Reuse the Stage 3.5A 2s open-position cache and a bounded correlation memo so the
    # calculation-only preview does not repeat DB round trips on every keystroke.
    try:
        open_pos = database.get_open_positions(ttl_sec=_PREVIEW_OPEN_POSITIONS_TTL_SEC)
        if not open_pos.empty:
            for _, pos in open_pos.iterrows():
                pos_sym = str(pos["symbol"]).upper()
                pos_dir = str(pos["direction"]).upper()
                if pos_sym != sym:
                    corr = get_pair_correlation(sym, pos_sym, ttl_sec=_PREVIEW_CORRELATION_TTL_SEC)
                    if abs(corr) >= 0.80:
                        same_dir = (direction in ["BUY", "LONG"] and "BUY" in pos_dir) or \
                                   (direction in ["SELL", "SHORT"] and "SELL" in pos_dir)
                        if corr > 0 and same_dir:
                            preview["warnings"].append(f"High positive correlation ({corr:.2f}) with open {pos_dir} on {pos_sym}. Adds compounding directional risk.")
                        elif corr < 0 and not same_dir:
                            preview["warnings"].append(f"High negative correlation ({corr:.2f}) with open {pos_dir} on {pos_sym}. Adds compounding directional risk.")
    except Exception:
        pass

    return preview

