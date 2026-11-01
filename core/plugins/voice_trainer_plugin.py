import json
import logging
import os
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# MUST define logger BEFORE any try/except that uses it
logger = logging.getLogger(__name__)

try:
    from core.memory import remember
except ImportError:
    remember = None
    logger.warning("[VoiceTrainer] core.memory.remember not found.")

try:
    from core.topic import detect_topic
except ImportError:
    def detect_topic(text):
        return "general"

MODEL_PATH = "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000

class Plugin:
    interactive = False

    def __init__(self):
        self.model = None
        self.recognizer = None
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(MODEL_PATH):
                self.model = Model(MODEL_PATH)
                self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
                logger.info("[VoiceTrainer] Vosk model loaded.")
            else:
                logger.warning(f"[VoiceTrainer] Model not found at {MODEL_PATH}")
        except Exception as e:
            logger.error(f"[VoiceTrainer] Load failed: {e}")

    def run(self):
        if self.model:
            logger.info("[VoiceTrainer] Ready. Use 'voice' command to start listening.")
        else:
            logger.warning("[VoiceTrainer] Model missing. Cannot start.")

    def start(self):
        if not self.recognizer:
            return "[VoiceTrainer] Model not loaded."
        logger.info("[VoiceTrainer] Listening... Speak now.")
        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=8000,
                dtype="int16",
                channels=1
            ) as stream:
                while True:
                    data, _ = stream.read(4000)
                    if self.recognizer.AcceptWaveform(bytes(data)):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            try:
                                if remember:
                                    remember(text, text, source="voice")
                            except Exception as e:
                                logger.error(f"[VoiceTrainer] Memory error: {e}")
                            logger.info(f"[VoiceTrainer] Saved: {text}")
                            return f"🎙️ Heard: {text}"
        except Exception as e:
            logger.error(f"[VoiceTrainer] Mic error: {e}")
            return f"[VoiceTrainer] Error: {e}"