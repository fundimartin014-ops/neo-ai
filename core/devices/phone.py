"""Phone dispatcher — routes `phone:` to Android or iOS."""
from __future__ import annotations
import logging

log = logging.getLogger("devices.phone")


def handle(text):
    t = (text or "").strip()
    if t.lower().startswith("ios "):
        from core.devices import phone_ios
        return phone_ios.handle(t[4:].strip())
    if t.lower().startswith("iphone "):
        from core.devices import phone_ios
        return phone_ios.handle(t[7:].strip())
    if t.lower() in ("ios", "iphone"):
        from core.devices import phone_ios
        return phone_ios.handle("status")
    from core.devices import phone_android
    return phone_android.handle(t)


def status_all():
    from core.devices import phone_android, phone_ios
    a = phone_android.AndroidPhone()
    i = phone_ios.iPhone()
    lines = ["[phone] summary"]
    if not a.is_available():
        lines.append("  android: adb not installed")
    else:
        lines.append(f"  android: {len(a.devices())} device(s)")
    if i.available():
        lines.append(f"  iphone:  ready via {i.notify_service}")
    else:
        lines.append("  iphone:  not configured")
    return "\n".join(lines)
