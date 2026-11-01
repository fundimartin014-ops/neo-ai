import time
from core.swarm_coordinator import SwarmCoordinator
from core.governor import approve
from core.governed_memory import store

class NeoDaemon:
    def __init__(self):
        self.swarm = SwarmCoordinator()
        self.running = True

    def handle_input(self, text):
        allowed, reason = approve(text)
        if not allowed:
            return reason

        answer = self.swarm.handle(text)
        store(answer, source="jarvis_mode")
        return answer

    def run(self):
        print("[Neo] J.A.R.V.I.S mode active")
        while self.running:
            time.sleep(0.2)  # keeps CPU low
