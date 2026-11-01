import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        # No API key required for general HTTP.
        logger.info("[HTTP] Plugin initialized. No key required.")

    def run(self):
        logger.info("HTTP Plugin ready. Use get(), post(), etc.")

    def get(self, url, timeout=10):
        try:
            r = requests.get(url, timeout=timeout)
            return {"status": r.status_code, "text": r.text[:3000], "url": url}
        except Exception as e:
            return {"error": str(e), "url": url}

    def post(self, url, data=None, json=None, timeout=10):
        try:
            r = requests.post(url, data=data, json=json, timeout=timeout)
            return {"status": r.status_code, "text": r.text[:3000], "url": url}
        except Exception as e:
            return {"error": str(e), "url": url}