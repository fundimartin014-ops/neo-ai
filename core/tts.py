import pyttsx3
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = pyttsx3.init()

def speak(text: str) -> None:
    """
    Convert text to speech with a small pause after punctuation.
    """
    logger.info("Speaking: %s", text)
    text = re.sub(r'([.!?])', r'\1 ', text)
    engine.say(text)
    engine.runAndWait()