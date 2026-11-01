import threading
import time
from core.web_search import search_web
from core.memory import remember


LEADERSHIP_TRACK = [
    "current president of kenya",
    "current president of usa",
    "current prime minister of uk"
]


def update_leadership():

    for query in LEADERSHIP_TRACK:
        result = search_web(query)

        if result and isinstance(result, dict):
            text = result["text"]

            remember(
                input_text=f"[AUTO UPDATE] {query}",
                response=text[:500],
                source="web",
                confidence=90
            )


def start_background_updater():

    def loop():
        while True:
            print("🔁 Autonomous leadership update running...")
            update_leadership()
            time.sleep(60 * 60 * 24)  # every 24 hours

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
