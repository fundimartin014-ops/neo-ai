import sounddevice as sd
import queue, json, sys
from vosk import Model, KaldiRecognizer

q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def listen(language="en"):
    model_path = f"models/{language}"
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)

    with sd.RawInputStream(samplerate=16000,
                           blocksize=8000,
                           dtype='int16',
                           channels=1,
                           callback=callback):
        print("🎤 Listening...")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    return text
