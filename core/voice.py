import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer

MODEL_PATH = "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000


def listen():
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1
    ) as stream:
        while True:
            data, _ = stream.read(4000)
            if recognizer.AcceptWaveform(bytes(data)):
                result = json.loads(recognizer.Result())
                return result.get("text", "")


def speak(text):
    print(f"[Neo]: {text}")
