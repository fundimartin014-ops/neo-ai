import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Voice/TTS placeholder.
    Vosk STT is handled by voice_trainer_plugin (fully offline, no key).
    This plugin can later be extended for pyttsx3 TTS.
    """
    def __init__(self):
        # No API key needed. Vosk is offline.
        logger.info("[Voice] Plugin initialized. No key required.")

    def run(self):
        logger.info("VoicePlugin ready. STT handled by voice_trainer.")

    def speak(self, text):
        """Placeholder for future TTS."""
        logger.info(f"[Voice TTS] Would speak: {text[:50]}...")
        return f"TTS placeholder: {text[:50]}..."