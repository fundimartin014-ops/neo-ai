"""irrigation_alert_plugin — pings you if the 3-day forecast is too dry.

Independent of the daily brief. Runs every N hours and pushes a
WhatsApp/Discord alert when total rain for the next 3 days is < threshold.

Env:
  IRRIGATION_ALERT_ENABLED=true        (default true)
  IRRIGATION_ALERT_LOCATION=Nakuru
  IRRIGATION_ALERT_HOURS=6             (check interval, default every 6h)
  IRRIGATION_DRY_THRESHOLD_MM=5.0
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger("irrigation_alert_plugin")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = PROJECT_ROOT / "data" / "irrigation_alert_state.json"


def _env_flag(name: str, default: bool = True) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


class Plugin:
    name = "irrigation_alert_plugin"

    def __init__(self):
        self.enabled = _env_flag("IRRIGATION_ALERT_ENABLED", True)
        self.location = (os.getenv("IRRIGATION_ALERT_LOCATION") or "Nakuru").strip()
        self.hours = float(os.getenv("IRRIGATION_ALERT_HOURS") or "6")
        self.threshold = float(os.getenv("IRRIGATION_DRY_THRESHOLD_MM") or "5.0")
        self._thread = None
        self._stop = threading.Event()

    def run(self) -> None:
        if not self.enabled:
            logger.info("[IrrigationAlert] disabled")
            return
        logger.info(
            "[IrrigationAlert] armed — %s every %.0fh (dry threshold %.1fmm)",
            self.location, self.hours, self.threshold,
        )

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._loop, name="IrrigationAlert", daemon=True
        )
        self._thread.start()
        logger.info("[IrrigationAlert] background thread started")

    def _loop(self) -> None:
        time.sleep(30)
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("[IrrigationAlert] tick failed: %s", e)
            self._stop.wait(self.hours * 3600)

    def _tick(self) -> None:
        from agents.locations import resolve_location
        hit = resolve_location(self.location)
        if hit is None:
            logger.warning("[IrrigationAlert] unknown location: %s", self.location)
            return
        lat, lon, name = hit

        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "daily": "precipitation_sum,temperature_2m_max",
                        "timezone": "Africa/Nairobi",
                        "forecast_days": 3,
                    },
                )
                r.raise_for_status()
                d = r.json().get("daily", {}) or {}
        except Exception as e:
            logger.warning("[IrrigationAlert] forecast fetch failed: %s", e)
            return

        precs = [p for p in (d.get("precipitation_sum") or []) if isinstance(p, (int, float))]
        if not precs:
            return
        total = sum(precs[:3])

        today = datetime.now().strftime("%Y-%m-%d")
        state = self._load_state()
        already = state.get("last_alert_date")
        should_alert = total < self.threshold and already != today

        if should_alert:
            self._notify(name, total, precs[:3])
            self._save_state({"last_alert_date": today, "total_mm": total})
            logger.info(
                "[IrrigationAlert] fired: %s total=%.1fmm (< %.1fmm)",
                name, total, self.threshold,
            )
        else:
            reason = "already alerted today" if already == today else "moisture OK"
            logger.info(
                "[IrrigationAlert] check: %s total=%.1fmm — %s",
                name, total, reason,
            )

    def _notify(self, location: str, total: float, daily: list) -> None:
        try:
            import asyncio
            from agents.notifiers import notify_brief

            days_str = ", ".join(f"{d:.1f}mm" for d in daily)
            body = (
                f"Only {total:.1f}mm rain forecast for {location} over the next 3 days "
                f"({days_str}). Irrigate tomorrow morning if you haven't already.\n\n"
                f"Threshold: {self.threshold}mm"
            )
            title = f"Irrigation Alert — {location} — {datetime.now().strftime('%Y-%m-%d')}"

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(asyncio.run, notify_brief(title, body)).result(timeout=20)
                else:
                    loop.run_until_complete(notify_brief(title, body))
            except RuntimeError:
                asyncio.run(notify_brief(title, body))
        except Exception as e:
            logger.warning("[IrrigationAlert] notify failed: %s", e)

    def _load_state(self) -> dict:
        try:
            if STATE_PATH.exists():
                return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_state(self, state: dict) -> None:
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        except Exception as e:
            logger.warning("[IrrigationAlert] state save failed: %s", e)

    def stop(self) -> None:
        self._stop.set()
