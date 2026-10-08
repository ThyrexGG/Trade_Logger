# -*- coding: utf-8 -*-
"""
Outbound transactional email — password-reset links only, today.

Plain SMTP via the stdlib ``smtplib`` / ``email`` modules, no third-party
service or SDK: same "stdlib does the job" spirit as ``api/auth.py``'s
hand-rolled scrypt. Works with any SMTP provider (a Gmail App Password, your
domain registrar's mailbox, Mailgun/SES/Resend's SMTP endpoint, ...).

Unconfigured is a valid state (local dev, or a box that hasn't set this up
yet): the email is skipped and logged instead of sent, so nothing breaks —
but password reset is not actually self-service for a stranger until
``TL_SMTP_HOST`` is set. See ``.env.example`` for the full variable list.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

log = logging.getLogger("tradelogger.email")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def smtp_configured() -> bool:
    return bool(_env("TL_SMTP_HOST"))


def app_url() -> str:
    """The public frontend origin, used to build links inside emails."""
    return _env("TL_PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")


def _from_address() -> str:
    return _env("TL_SMTP_FROM") or _env("TL_SMTP_USER") or "no-reply@tradelogger.site"


def _from_header() -> str:
    name = _env("TL_SMTP_FROM_NAME", "TradeLogger")
    return f"{name} <{_from_address()}>"


def send_email(to: str, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
    """Best-effort send. Returns ``False`` (and logs) on any failure, or when
    SMTP isn't configured. Never raises — a mail-server hiccup must not break
    the request that triggered it. Callers must not let the return value
    change what they tell the caller (see ``request_password_reset``'s
    no-enumeration contract) — this is purely for the server's own logs."""
    if not to or "@" not in to:
        return False
    if not smtp_configured():
        log.warning("TL_SMTP_HOST not set — skipping email to %s: %s", to, subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_header()
    msg["To"] = to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    host = _env("TL_SMTP_HOST")
    try:
        port = int(_env("TL_SMTP_PORT", "587") or "587")
    except ValueError:
        port = 587
    user = _env("TL_SMTP_USER")
    password = _env("TL_SMTP_PASSWORD")
    use_ssl = _env("TL_SMTP_SSL", "0").lower() in ("1", "true", "yes")

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                if user:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls(context=ssl.create_default_context())
                if user:
                    server.login(user, password)
                server.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - email delivery must never raise to the caller
        log.exception("failed to send email to %s", to)
        return False


def send_password_reset(to: str, token: str) -> bool:
    link = f"{app_url()}/?reset_token={token}"
    text = (
        "Someone requested a password reset for your TradeLogger account.\n\n"
        f"Reset your password: {link}\n\n"
        "This link expires in 30 minutes and works once.\n\n"
        "If you didn't request this, ignore this email — your password won't change."
    )
    body = (
        '<p style="margin:0 0 16px">Someone requested a password reset for your TradeLogger account.</p>'
        f'<p style="margin:0 0 20px"><a href="{link}" style="{_BUTTON}">Reset your password</a></p>'
        '<p style="margin:0;color:#5b6779;font-size:12px">This link expires in 30 minutes and works once. '
        "If you didn't request this, ignore this email — your password won't change.</p>"
    )
    return send_email(to, "Reset your TradeLogger password", text, _branded(body, link))


# Brand styling for HTML email (docs/BRAND.md). Email clients ignore <style>
# blocks and CSS variables, so everything is inline and light-ground: dark
# mode clients invert light emails reliably, but mangle dark ones.
_BUTTON = (
    "display:inline-block;background:#0a6f94;color:#ffffff;text-decoration:none;"
    "font-weight:600;font-size:14px;padding:10px 18px;border-radius:8px"
)


def _branded(body_html: str, link: str) -> str:
    """Wrap an email body in the TradeLogger header/footer."""
    icon = f"{app_url()}/icon-192.png"
    return (
        '<div style="background:#f4f6fa;padding:32px 16px;'
        "font-family:Geist,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0e1726\">"
        '<div style="max-width:480px;margin:0 auto">'
        '<p style="margin:0 0 16px;font-size:15px;font-weight:600;letter-spacing:-0.01em">'
        f'<img src="{icon}" width="24" height="24" alt="" '
        'style="vertical-align:middle;border-radius:6px;margin-right:8px">TradeLogger</p>'
        '<div style="background:#ffffff;border:1px solid #dde3ec;border-radius:10px;padding:24px;'
        'font-size:14px;line-height:1.55">'
        f"{body_html}"
        "</div>"
        '<p style="margin:16px 0 0;color:#5b6779;font-size:11px;line-height:1.5">'
        f'Button not working? Paste this into your browser:<br><span style="word-break:break-all">{link}</span></p>'
        "</div></div>"
    )
