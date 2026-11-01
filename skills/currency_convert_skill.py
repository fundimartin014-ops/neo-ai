import logging
import time
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Free public APIs, tried in order. No keys required.
_APIS = [
    "https://api.exchangerate.host/convert",
    "https://open.er-api.com/v6/latest/{base}",
]

_CACHE = {}  # {(from, to): (rate, timestamp)}
_CACHE_TTL = 300  # 5 minutes


class CurrencyConvertSkill:
    """
    Multi-API currency converter with in-process cache.
    Tries exchangerate.host → open.er-api.com → fails cleanly.
    """

    def __init__(self):
        pass

    def _cache_get(self, src, tgt):
        k = (src, tgt)
        v = _CACHE.get(k)
        if v and time.time() - v[1] < _CACHE_TTL:
            return v[0]
        return None

    def _cache_set(self, src, tgt, rate):
        _CACHE[(src, tgt)] = (rate, time.time())

    def _try_exchangerate_host(self, src, tgt, amount):
        r = requests.get(
            "https://api.exchangerate.host/convert",
            params={"from": src, "to": tgt, "amount": amount},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        rate = data.get("info", {}).get("rate")
        if result is None and rate is not None:
            result = amount * rate
        return (result, rate) if result is not None else (None, None)

    def _try_er_api(self, src, tgt, amount):
        r = requests.get(f"https://open.er-api.com/v6/latest/{src}", timeout=10)
        r.raise_for_status()
        data = r.json()
        rates = data.get("rates", {})
        rate = rates.get(tgt)
        if rate is None:
            return (None, None)
        return (amount * rate, rate)

    def process(self, inputs: dict) -> dict:
        src = str(inputs.get("from", "USD")).upper()
        tgt = str(inputs.get("to", "EUR")).upper()
        try:
            amount = float(inputs.get("amount", 1))
        except (TypeError, ValueError):
            return {"error": "amount must be a number"}

        if src == tgt:
            return {"converted": amount, "from": src, "to": tgt, "rate": 1.0, "method": "identity"}

        # Cache hit
        cached_rate = self._cache_get(src, tgt)
        if cached_rate is not None:
            return {
                "converted": amount * cached_rate,
                "from": src, "to": tgt, "rate": cached_rate, "method": "cache",
            }

        errors = []
        for fn in (self._try_exchangerate_host, self._try_er_api):
            try:
                result, rate = fn(src, tgt, amount)
                if result is not None and rate is not None:
                    self._cache_set(src, tgt, rate)
                    return {
                        "converted": result,
                        "from": src, "to": tgt, "rate": rate,
                        "method": fn.__name__.replace("_try_", ""),
                    }
            except Exception as e:
                errors.append(f"{fn.__name__}: {e}")

        return {"error": "All currency APIs failed", "detail": errors[:2]}