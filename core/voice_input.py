import vosk
import sounddevice as sd
import queue
import json

q = queue.Queue()
model = None
MODEL_PATH = "vosk-model-small-en-us-0.15"


def get_model():
    global model
    if model is None:
        model = vosk.Model(MODEL_PATH)
    return model

def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))

def listen():
    """Offline voice recognition, returns transcribed text."""
    rec = vosk.KaldiRecognizer(get_model(), 16000)
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1, callback=callback):
        print("[Neo] Listening...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                return result.get("text", "")
