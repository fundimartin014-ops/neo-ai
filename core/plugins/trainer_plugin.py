import logging
from core.memory import remember
from core.topic import detect_topic

logger = logging.getLogger(__name__)

class Plugin:
    interactive = False  # CRITICAL: do NOT block launcher startup

    def run(self):
        logger.info("[Trainer] Ready. Use 'train <text>' command.")

    def train(self, text):
        if not text:
            return "⚠️ Empty training text."
        remember(text, text, source="manual", meta={"topic": detect_topic(text)})
        return f"✅ Trained: {text[:50]}..."