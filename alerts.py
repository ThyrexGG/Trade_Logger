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

def notify_trade_closed(trade):
    """Dispatches a push notification when a trade is closed."""
    pnl = float(trade.get("net_profit", 0.0))
    pnl_sign = "+" if pnl >= 0 else "-"
    sym = str(trade.get("symbol", "")).upper()
    dir_str = str(trade.get("direction", "")).upper()
    dur = float(trade.get("duration_minutes", 0.0))
    dur_str = f"{dur:.1f}m" if dur < 60 else f"{dur/60:.1f}h"
    acc = str(trade.get("account_id", ""))
    acc_label = "Funded MT5" if acc.startswith("MT5_") else "Capital Real"
    
    title = f"Trade Closed: {sym} ({pnl_sign}${abs(pnl):,.2f})"
    msg = f"{acc_label} • {dir_str} • PnL: {pnl_sign}${abs(pnl):,.2f} • Duration: {dur_str}"
    
    # 1. Native Windows Desktop Notification
    send_windows_toast(title, msg)

    # 2. Native Push
    send_onesignal_push(title, msg, data=trade)
    
    # 2. Telegram Bot Alert
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
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

def notify_risk_warning(account_id, current_loss, limit):
    """Dispatches high-priority alert when daily loss reaches dangerous levels."""
    pct = (abs(current_loss) / limit) * 100
    title = f"⚠️ RISK WARNING: {pct:.0f}% of Daily Limit Hit"
    msg = f"Current Daily Drawdown: -${abs(current_loss):,.2f} / ${limit:,.0f} limit. Stop trading to protect funded account!"
    
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

if __name__ == "__main__":
    print("Alert module ready.")
