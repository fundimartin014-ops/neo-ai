import threading
import time


class BackgroundLoop:
    def __init__(self, brain, interval_seconds=30):
        self.brain = brain
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("[Background] Autonomous loop started")

    def stop(self):
        self.running = False
        print("[Background] Autonomous loop stopped")

    def _run(self):
        while self.running:
            try:
                if hasattr(self.brain, "agent") and hasattr(self.brain.agent, "run_goal_cycle"):
                    out = self.brain.agent.run_goal_cycle()
                    if out:
                        print(f"[Background] {out}")
                time.sleep(self.interval_seconds)
            except Exception as e:
                print("[Background Error]", e)
                time.sleep(5)