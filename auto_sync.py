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
                    alerts.notify_trade_closed(row.to_dict())
                    known_trade_ids.add(row["trade_id"])
                    logfn(f"Alert sent for trade {row['trade_id']} ({row['symbol']} PnL: ${row['net_profit']:.2f})")
    except Exception as alert_err:  # noqa: BLE001
        result["errors"].append(f"push: {alert_err}")
        logfn(f"Alert dispatch error: {alert_err}")

    # 4. Active price alerts
    try:
        active_alerts = database.get_active_price_alerts()
        if active_alerts:
            _mt5_ok = mt5_sync.MT5_AVAILABLE
            try:
                import mt5_gate
                _mt5_ok = _mt5_ok and mt5_gate.is_mt5_enabled()
            except Exception:
                pass
            for alert in active_alerts:
                sym = alert["symbol"]
                target = float(alert["target_price"])
                cond = alert["condition"]
                current_price = None
                if _mt5_ok:
                    try:
                        import MetaTrader5 as mt5
                        tick = mt5.symbol_info_tick(sym)
                        if tick:
                            current_price = float(tick.bid)
                    except Exception:
                        pass
                if current_price is not None:
                    triggered = (cond == "ABOVE" and current_price >= target) or \
                                (cond == "BELOW" and current_price <= target)
                    if triggered:
                        logfn(f"Price alert triggered! {sym} at {current_price} ({cond} {target})")
                        alerts.notify_price_alert(sym, current_price, target, cond, alert.get("notes", ""))
                        database.mark_price_alert_triggered(alert["id"])
    except Exception as price_alert_err:  # noqa: BLE001
        result["errors"].append(f"price_alerts: {price_alert_err}")
        logfn(f"Price alert check error: {price_alert_err}")

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
