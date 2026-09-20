import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

LOG_FILE = os.path.join(os.path.dirname(__file__), "sync_log.txt")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

import mt5_sync
import capital_sync
import database
import alerts

SYNC_INTERVAL_SECONDS = 30  # Sync every 30 seconds for live floating PnL and trade updates

# When the API server's in-process sync service is running it writes a heartbeat
# here; this standalone daemon stands down for cycles where that heartbeat is
# fresh so the two never double-sync the brokers.
_INPROCESS_HEARTBEAT_KEY = "inprocess_sync_heartbeat"
_INPROCESS_HEARTBEAT_STALE_SEC = 90


def _inprocess_sync_active() -> bool:
    try:
        raw = database.get_setting(_INPROCESS_HEARTBEAT_KEY, "")
        if not raw:
            return False
        ts = datetime.fromisoformat(raw)
        age = (datetime.now(ts.tzinfo) - ts).total_seconds()
        return age < _INPROCESS_HEARTBEAT_STALE_SEC
    except Exception:
        return False


def _alert_price(sym: str, mt5_ok: bool, cache: dict):
    """Current price for one alert symbol, or None when no REAL quote is available.
    MT5 tick first (when the terminal is enabled), then the verified public feeds.
    Never a placeholder: a made-up price must not be able to trigger an alert."""
    if sym in cache:
        return cache[sym]
    price = None
    if mt5_ok:
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(sym)
            if tick:
                price = float(tick.bid)
        except Exception:
            price = None
    if price is None:
        try:
            import market_data
            price = market_data.get_verified_price(sym)
        except Exception:
            price = None
    cache[sym] = price
    return price


def _tenant_owns_global_channels() -> bool:
    """Telegram / Discord / Windows toast are configured once, in the server's env, for
    the owner. Another user's alert must never be posted there (only pushed to their own
    devices via the trade-event feed)."""
    try:
        from api import sync_service
        import tenant
        return sync_service._env_fallback_ok(tenant.current_user_id())
    except Exception:
        return False


def check_price_alerts(logfn=log) -> int:
    """Evaluate the current tenant's ACTIVE price alerts against live prices and fire
    the ones that crossed. Returns how many fired."""
    active_alerts = database.get_active_price_alerts()
    if not active_alerts:
        return 0
    mt5_ok = mt5_sync.MT5_AVAILABLE
    try:
        import mt5_gate
        mt5_ok = mt5_ok and mt5_gate.is_mt5_enabled()
    except Exception:
        pass
    prices: dict = {}
    fired = 0
    for alert in active_alerts:
        sym = alert["symbol"]
        target = float(alert["target_price"])
        cond = alert["condition"]
        current_price = _alert_price(sym, mt5_ok, prices)
        if current_price is None:
            continue
        triggered = (cond == "ABOVE" and current_price >= target) or                     (cond == "BELOW" and current_price <= target)
        if not triggered:
            continue
        logfn(f"Price alert triggered! {sym} at {current_price} ({cond} {target})")
        database.mark_price_alert_triggered(alert["id"])  # first, so a notify failure can't re-fire it every cycle
        fired += 1
        import trade_notify
        trade_notify.record_price_alert(sym, current_price, target, cond, alert["id"])
        if _tenant_owns_global_channels():
            alerts.notify_price_alert(sym, current_price, target, cond, alert.get("notes", ""))
    return fired


def run_sync_cycle(known_trade_ids: set, logfn=log, creds: dict | None = None) -> dict:
    """One sync iteration — Capital.com trade/position sync, closed-trade push
    alerts, and price-alert checks (plus MT5 only if MT5_ENABLED). Shared by
    this standalone daemon and the API server's in-process sync service.
    `known_trade_ids` is mutated in place with any newly seen closed trades.
    `creds` (W8.6): a specific user's Capital.com credentials; None uses the
    CAPITAL_* environment (single-user / owner). MT5 always uses the local
    terminal and is unaffected."""
    result = {"mt5_ok": False, "mt5_skipped": False, "capital_ok": False,
              "new_closed_trades": 0, "errors": []}

    # 1. Sync MetaTrader 5 — only when explicitly enabled (MT5_ENABLED). The
    #    local terminals were uninstalled, so this is off by default.
    try:
        import mt5_gate
        mt5_on = mt5_gate.is_mt5_enabled()
    except Exception:
        mt5_on = False
    if not mt5_on:
        result["mt5_skipped"] = True
    else:
        try:
            result["mt5_ok"] = bool(mt5_sync.sync_mt5())
            logfn("MT5 Sync: SUCCESS" if result["mt5_ok"]
                  else "MT5 Sync: Completed (no new trades or terminal busy)")
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"mt5: {e}")
            logfn(f"MT5 Sync Exception: {e}")

    # 2. Sync Capital.com
    try:
        result["capital_ok"] = bool(capital_sync.sync_capital(creds=creds))
        logfn("Capital.com Sync: SUCCESS" if result["capital_ok"]
              else "Capital.com Sync: Completed (no new trades)")
    except Exception as e:  # noqa: BLE001
        result["errors"].append(f"capital: {e}")
        logfn(f"Capital.com Sync Exception: {e}")

    # 3. Newly closed trades -> push notifications
    try:
        current_df = database.get_closed_trades(ttl_sec=database.CACHE_TTL_CLOSED_TRADES)
        if not current_df.empty:
            new_trades = current_df[~current_df["trade_id"].isin(known_trade_ids)]
            result["new_closed_trades"] = int(len(new_trades))
            if not new_trades.empty:
                logfn(f"Detected {len(new_trades)} newly closed trades! Dispatching push alerts...")
                for _, row in new_trades.iterrows():
                    try:  # server-side event -> phone push + desktop notification
                        import trade_notify
                        trade_notify.record_closed(row.to_dict())
                    except Exception as event_err:  # noqa: BLE001
                        logfn(f"Trade event error: {event_err}")
                    alerts.notify_trade_closed(row.to_dict())
                    known_trade_ids.add(row["trade_id"])
                    logfn(f"Alert sent for trade {row['trade_id']} ({row['symbol']} PnL: ${row['net_profit']:.2f})")
    except Exception as alert_err:  # noqa: BLE001
        result["errors"].append(f"push: {alert_err}")
        logfn(f"Alert dispatch error: {alert_err}")

    # 4. Active price alerts
    try:
        check_price_alerts(logfn)
    except Exception as price_alert_err:  # noqa: BLE001
        result["errors"].append(f"price_alerts: {price_alert_err}")
        logfn(f"Price alert check error: {price_alert_err}")

    # 5. Loss limits (daily loss / drawdown) -> notification when a limit is approached or reached
    try:
        from api import loss_limits
        loss_limits.check(logfn)
    except Exception as limit_err:  # noqa: BLE001
        result["errors"].append(f"loss_limits: {limit_err}")
        logfn(f"Loss limit check error: {limit_err}")

    # 6. Weekly performance summary (sends at most once a week per user, and only inside its send window)
    try:
        from api import weekly_summary
        weekly_summary.check(logfn)
    except Exception as summary_err:  # noqa: BLE001
        result["errors"].append(f"weekly_summary: {summary_err}")
        logfn(f"Weekly summary check error: {summary_err}")

    return result


def run_auto_sync():
    log("TRADELOGGER AUTOMATIC CLOUD SYNC & PUSH ALERTS DAEMON STARTED")
    log(f"Interval: Every {SYNC_INTERVAL_SECONDS} seconds")

    # Initialize known trades cache
    try:
        df_init = database.get_closed_trades()
        known_trade_ids = set(df_init["trade_id"].tolist()) if not df_init.empty else set()
        log(f"Loaded {len(known_trade_ids)} initial trades into alert cache.")
    except Exception as e:
        known_trade_ids = set()
        log(f"Cache init warning: {e}")

    while True:
        if _inprocess_sync_active():
            log("In-process sync service is active — standing down this cycle.")
        else:
            log("Starting sync cycle...")
            run_sync_cycle(known_trade_ids)

        log(f"Sleeping for {SYNC_INTERVAL_SECONDS}s...")
        time.sleep(SYNC_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        run_auto_sync()
    except Exception as exc:
        log(f"CRITICAL DAEMON CRASH: {exc}")
