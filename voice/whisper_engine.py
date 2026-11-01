# core/voice/whisper_engine.py
from faster_whisper import WhisperModel

class WhisperEngine:
    def __init__(self, model_size="base"):
        # tiny, base, small, medium, large-v3
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
    def transcribe(self, audio_path: str) -> str:
        segments, info = self.model.transcribe(audio_path, beam_size=5)
        return " ".join([s.text for s in segments])