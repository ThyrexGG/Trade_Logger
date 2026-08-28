import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID", "").strip('"\' ')
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY", "").strip('"\' ')
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        if "ONESIGNAL_APP_ID" in st.secrets:
            ONESIGNAL_APP_ID = str(st.secrets["ONESIGNAL_APP_ID"]).strip('"\' ')
        if "ONESIGNAL_API_KEY" in st.secrets:
            ONESIGNAL_API_KEY = str(st.secrets["ONESIGNAL_API_KEY"]).strip('"\' ')
except Exception:
    pass
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip('"\' ')
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip('"\' ')

def send_onesignal_push(title, message, data=None):
    """Sends native push notification to mobile devices via OneSignal REST API."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        return False
        
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "headings": {"en": title},
        "contents": {"en": message},
        "data": data or {},
        "small_icon": "ic_launcher",
        "android_accent_color": "FF00FFCC",
        "priority": 10
    }
    
    try:
        resp = requests.post("https://onesignal.com/api/v1/notifications", json=payload, headers=headers, timeout=8)
        return resp.status_code == 200
    except Exception as e:
        print(f"OneSignal push error: {e}")
        return False

def send_telegram_alert(message_markdown):
    """Sends formatted Telegram message with markdown styling."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_markdown,
        "parse_mode": "HTML"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=8)
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram alert error: {e}")
        return False

def send_windows_toast(title, message):
    """Sends native Windows 10/11 desktop notification banner."""
    if os.name == 'nt':
        try:
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), "send_toast.ps1")
            if os.path.exists(script_path):
                subprocess.Popen(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Title", str(title), "-Message", str(message)],
                    creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                return True
        except Exception as e:
            print(f"Windows toast error: {e}")
    return False

import json

RULES_FILE = os.path.join(os.path.dirname(__file__), "alert_rules.json")

DEFAULT_RULES = {
    "big_win_threshold": 100.0,
    "max_loss_threshold": 50.0,
    "daily_drawdown_limit": 300.0,
    "streak_alert_target": 3,
    "notify_on_all_trades": True,
    "filter_account": "ALL"
}

def get_alert_rules():
    """Loads custom notification rules from JSON file or default fallback."""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                res = DEFAULT_RULES.copy()
                res.update(saved)
                return res
        except Exception:
            return DEFAULT_RULES.copy()
    return DEFAULT_RULES.copy()

def save_alert_rules(rules):
    """Saves custom notification rules to JSON file."""
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving alert rules: {e}")
        return False

def notify_trade_closed(trade, rules=None):
    """Dispatches a push notification when a trade is closed with custom rule evaluations."""
    if rules is None:
        rules = get_alert_rules()
        
    pnl = float(trade.get("net_profit", 0.0))
    pnl_sign = "+" if pnl >= 0 else "-"
    sym = str(trade.get("symbol", "")).upper()
    dir_str = str(trade.get("direction", "")).upper()
    dur = float(trade.get("duration_minutes", 0.0))
    dur_str = f"{dur:.1f}m" if dur < 60 else f"{dur/60:.1f}h"
    acc = str(trade.get("account_id", ""))
    acc_label = "Funded MT5" if acc.startswith("MT5_") else "Capital Real"
    is_win = pnl >= 0
    
    # Custom Rule 1: Big Win Target Alert
    big_win_thresh = float(rules.get("big_win_threshold", 100.0))
    # Custom Rule 2: Max Loss Alert
    max_loss_thresh = float(rules.get("max_loss_threshold", 50.0))
    
    if is_win and pnl >= big_win_thresh:
        title = f"🎯 BIG WIN: +${pnl:,.2f} • {sym}"
        msg = f"Target Exceeded! {dir_str} on {acc_label} • Net PnL: +${pnl:,.2f} • Held: {dur_str}"
    elif not is_win and abs(pnl) >= max_loss_thresh:
        title = f"⚠️ MAX LOSS ALERT: -${abs(pnl):,.2f} • {sym}"
        msg = f"Risk Limit Exceeded! {dir_str} on {acc_label} • Net PnL: -${abs(pnl):,.2f} • Held: {dur_str}"
    else:
        status_label = "Profit" if is_win else "Loss"
        emoji = "🟢" if is_win else "🔴"
        title = f"{emoji} {status_label}: {pnl_sign}${abs(pnl):,.2f} • {sym}"
        msg = f"{dir_str} on {acc_label} • Net PnL: {pnl_sign}${abs(pnl):,.2f} • Held: {dur_str}"
    
    # Check if notify_on_all_trades is enabled or if threshold was met
    if rules.get("notify_on_all_trades", True) or (is_win and pnl >= big_win_thresh) or (not is_win and abs(pnl) >= max_loss_thresh):
        send_windows_toast(title, msg)
        send_onesignal_push(title, msg, data=trade)
        
        pnl_emoji = "🟢" if is_win else "🔴"
        tg_text = (
            f"<b>{pnl_emoji} Trade Closed: {sym}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Account:</b> {acc_label}\n"
            f"<b>Direction:</b> {dir_str}\n"
            f"<b>Net PnL:</b> <b>{pnl_sign}${abs(pnl):,.2f}</b>\n"
            f"<b>Duration:</b> {dur_str}\n"
            f"<b>Entry:</b> {trade.get('entry_price', 0):.5f} ➔ <b>Exit:</b> {trade.get('exit_price', 0):.5f}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_alert(tg_text)
    
    return title, msg

def notify_risk_warning(account_id, current_loss, limit):
    """Dispatches high-priority alert when daily loss reaches dangerous levels."""
    pct = (abs(current_loss) / limit) * 100
    title = f"⚠️ RISK WARNING: {pct:.0f}% of Daily Limit Hit"
    msg = f"Current Daily Drawdown: -${abs(current_loss):,.2f} / ${limit:,.0f} limit. Stop trading to protect funded account!"
    
    send_windows_toast(title, msg)
    send_onesignal_push(title, msg)
    
    tg_text = (
        f"🚨 <b>PROP FIRM RISK GUARDIAN</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Warning:</b> Daily loss reached <b>{pct:.1f}%</b> of limit!\n"
        f"<b>Current Drawdown:</b> -${abs(current_loss):,.2f}\n"
        f"<b>Daily Floor Limit:</b> ${limit:,.0f}\n"
        f"<b>Recommendation:</b> Stop trading immediately to protect your evaluation account!\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    send_telegram_alert(tg_text)
    return title, msg

def notify_price_alert(symbol, current_price, target_price, condition, notes=""):
    """Dispatches high-priority alert when a live market price crosses an alert target."""
    sym = str(symbol).upper()
    cond_label = "rose above" if str(condition).upper() == "ABOVE" else "dropped below"
    title = f"🔔 Price Alert: {sym} reached ${current_price:,.2f}"
    msg = f"{sym} {cond_label} target ${target_price:,.2f} (Current: ${current_price:,.2f})"
    if notes:
        msg += f" • Note: {notes}"
        
    send_windows_toast(title, msg)
    send_onesignal_push(title, msg, data={"symbol": sym, "price": current_price, "target": target_price})
    
    tg_text = (
        f"🔔 <b>PRICE ALERT TRIGGERED: {sym}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Current Price:</b> <b>${current_price:,.2f}</b>\n"
        f"<b>Target Level:</b> ${target_price:,.2f} ({condition})\n"
    )
    if notes:
        tg_text += f"<b>Notes:</b> {notes}\n"
    tg_text += "━━━━━━━━━━━━━━━━━━"
    send_telegram_alert(tg_text)
    return title, msg

if __name__ == "__main__":
    print("Alert module ready with Price Alerts and Custom Rules Engine.")
