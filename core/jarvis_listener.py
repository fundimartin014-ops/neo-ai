from core.voice_input import listen
from core.wake_word import detect

def wait_for_command():
    text = listen()
    if not text:
        return None

    if detect(text):
        cleaned = text.replace("neo", "").replace("hey", "").strip()
        return cleaned

    return None
