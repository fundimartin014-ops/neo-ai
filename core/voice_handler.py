from core.swarm_coordinator import SwarmCoordinator
from core.jarvis_listener import wait_for_command
from core.normalize import normalize

neo = None


def get_neo():
    global neo
    if neo is None:
        neo = SwarmCoordinator()
    return neo

def handle_voice():
    text = wait_for_command()  # Offline voice input
    if not text:
        return

    text = normalize(text)
    answer = get_neo().handle(text)
    print(f"Neo: {answer}")
