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
    html = (
        "<p>Someone requested a password reset for your TradeLogger account.</p>"
        f'<p><a href="{link}">Reset your password</a></p>'
        '<p style="color:#888;font-size:12px">This link expires in 30 minutes and works once. '
        "If you didn't request this, ignore this email — your password won't change.</p>"
    )
    return send_email(to, "Reset your TradeLogger password", text, html)
