"""SMS plugin — Africa''s Talking primary, Twilio fallback.

Env vars (either set works):
  Africa''s Talking:  AT_USERNAME, AT_API_KEY, AT_SENDER_ID (optional)
  Twilio:             TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM

Usage from chat:
  sms: +254712345678 Hello from Neo
"""
from __future__ import annotations
import os
import re
import logging

log = logging.getLogger("sms_plugin")

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class Plugin:
    name = "sms"

    def __init__(self):
        self.at_user = os.getenv("AT_USERNAME", "").strip()
        self.at_key = os.getenv("AT_API_KEY", "").strip()
        self.at_sender = os.getenv("AT_SENDER_ID", "").strip()
        self.tw_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.tw_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.tw_from = os.getenv("TWILIO_FROM", "").strip()
        backends = []
        if self.at_user and self.at_key:
            backends.append("africastalking")
        if self.tw_sid and self.tw_token and self.tw_from:
            backends.append("twilio")
        self.backends = backends
        log.info("[SMS] Plugin initialized. Backends: %s",
                 ", ".join(backends) if backends else "none (set AT_* or TWILIO_* env)")

    def run(self):
        return "SMS plugin ready." if self.backends else \
               "SMS plugin idle — no backend configured."

    # ---------- core send ----------
    def send(self, to: str, body: str) -> str:
        to = self._normalize_phone(to)
        if not to:
            return "[SMS] invalid phone number"
        if not body or not body.strip():
            return "[SMS] empty message body"
        for backend in self.backends:
            try:
                if backend == "africastalking":
                    r = self._send_at(to, body)
                    if r: return r
                elif backend == "twilio":
                    r = self._send_twilio(to, body)
                    if r: return r
            except Exception as e:
                log.warning("[SMS] %s failed: %s", backend, e)
        if not self.backends:
            return ("[SMS] no backend configured. Set AT_USERNAME + AT_API_KEY "
                    "or TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM "
                    "in .env, then restart.")
        return "[SMS] all backends failed — check logs"

    # ---------- backends ----------
    def _send_at(self, to: str, body: str) -> str:
        if not _HAS_REQUESTS:
            return ""
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "apiKey": self.at_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"username": self.at_user, "to": to, "message": body}
        if self.at_sender:
            data["from"] = self.at_sender
        r = requests.post(url, headers=headers, data=data, timeout=15)
        if r.status_code >= 300:
            log.warning("[SMS] AT HTTP %s: %s", r.status_code, r.text[:200])
            return ""
        j = r.json()
        recips = (j.get("SMSMessageData") or {}).get("Recipients") or []
        if recips:
            status = recips[0].get("status", "?")
            return f"[SMS] sent via Africa's Talking to {to} ({status})"
        return f"[SMS] sent via Africa's Talking to {to}"

    def _send_twilio(self, to: str, body: str) -> str:
        if not _HAS_REQUESTS:
            return ""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.tw_sid}/Messages.json"
        r = requests.post(url,
                          auth=(self.tw_sid, self.tw_token),
                          data={"To": to, "From": self.tw_from, "Body": body},
                          timeout=15)
        if r.status_code >= 300:
            log.warning("[SMS] Twilio HTTP %s: %s", r.status_code, r.text[:200])
            return ""
        return f"[SMS] sent via Twilio to {to}"

    # ---------- helpers ----------
    @staticmethod
    def _normalize_phone(p: str) -> str:
        if not p:
            return ""
        p = re.sub(r"[^\d+]", "", str(p))
        if p.startswith("0") and len(p) == 10:
            p = "+254" + p[1:]   # Kenya default
        elif p.startswith("254") and not p.startswith("+"):
            p = "+" + p
        if not re.match(r"^\+\d{8,15}$", p):
            return ""
        return p

    # ---------- agent-style interface ----------
    def process(self, query=None, inputs=None, **kw):
        text = ""
        for c in (query, kw.get("text"), kw.get("message")):
            if isinstance(c, str) and c.strip():
                text = c.strip(); break
        if isinstance(inputs, dict):
            text = (inputs.get("to", "") + " " + inputs.get("body", "")).strip() or text
        if not text:
            return "Usage: sms: <phone> <message>"
        m = re.match(r"^(\+?[\d\s\-]{7,20})\s+(.+)$", text)
        if not m:
            return "Usage: sms: <phone> <message>"
        return self.send(m.group(1), m.group(2))

    def handle(self, query=None, **kw):
        return self.process(query=query, **kw)
