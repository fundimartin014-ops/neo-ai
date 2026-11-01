"""Multi-channel notifications.

Env vars:
  DISCORD_WEBHOOK_URL   discord.com/api/webhooks/...
  SLACK_WEBHOOK_URL     hooks.slack.com/services/...
  GENERIC_WEBHOOK_URL   any HTTP endpoint; posts {"text": "..."} JSON
  SMTP_HOST             e.g. smtp.gmail.com
  SMTP_PORT             e.g. 587
  SMTP_USER             your email
  SMTP_PASS             app password
  SMTP_TO               comma-separated recipients
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger(__name__)
_MAX = 1900


async def _post_json(url: str, payload: dict, timeout: int = 10) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
        return True
    except Exception as e:
        logger.warning("webhook post failed (%s): %s", url[:40], e)
        return False


async def discord_notify(text: str, url: str | None = None) -> bool:
    u = (url or os.getenv("DISCORD_WEBHOOK_URL", "")).strip()
    if not u:
        return False
    if len(text) > _MAX:
        text = text[:_MAX] + "\n... (truncated)"
    return await _post_json(u, {"content": text})


async def slack_notify(text: str, url: str | None = None) -> bool:
    u = (url or os.getenv("SLACK_WEBHOOK_URL", "")).strip()
    if not u:
        return False
    if len(text) > _MAX:
        text = text[:_MAX] + "\n... (truncated)"
    return await _post_json(u, {"text": text})


async def generic_notify(text: str, url: str | None = None) -> bool:
    u = (url or os.getenv("GENERIC_WEBHOOK_URL", "")).strip()
    if not u:
        return False
    return await _post_json(u, {"text": text})


def _send_email_blocking(subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    to = [a.strip() for a in os.getenv("SMTP_TO", "").split(",") if a.strip()]
    if not (host and user and pwd and to):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception as e:
        logger.warning("smtp send failed: %s", e)
        return False


async def email_notify(subject: str, body: str) -> bool:
    import asyncio
    return await asyncio.to_thread(_send_email_blocking, subject, body)


async def notify(text: str, subject: str = "Neo notification") -> dict[str, bool]:
    """Fan out to every configured channel. Returns per-channel results."""
    results = {
        "discord":  await discord_notify(text),
        "slack":    await slack_notify(text),
        "webhook":  await generic_notify(text),
        "email":    await email_notify(subject, text),
        "whatsapp": await whatsapp_notify(text),
    }
    if not any(results.values()):
        logger.info("NOTIFY (no channel configured): %s", text)
    return results


async def notify_brief(title: str, body: str) -> dict[str, bool]:
    """Slightly richer API for briefs (subject + body, markdown-friendly)."""
    text = f"**{title}**\n\n{body}"
    return await notify(text, subject=title)

# ---------------------------------------------------------------------------
# WhatsApp via Twilio
#   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
#   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
#   TWILIO_WHATSAPP_TO=whatsapp:+254...
# ---------------------------------------------------------------------------
async def whatsapp_notify(text: str, to: str | None = None) -> bool:
    sid   = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    frm   = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    dst   = (to or os.getenv("TWILIO_WHATSAPP_TO", "")).strip()
    if not all([sid, token, frm, dst]):
        return False
    if len(text) > 1500:
        text = text[:1500] + "\n... (truncated)"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        async with httpx.AsyncClient(timeout=15, auth=(sid, token)) as client:
            r = await client.post(url, data={"From": frm, "To": dst, "Body": text})
            r.raise_for_status()
        return True
    except Exception as e:
        logger.warning("whatsapp_notify failed: %s", e)
        return False
