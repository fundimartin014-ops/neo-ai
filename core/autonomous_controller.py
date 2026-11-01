import threading
import time

class AutonomousController:

    def __init__(self, brain):

        self.brain = brain
        self.running = False

    def start(self):

        if self.running:
            return "Autonomous mode already running."

        self.running = True

        thread = threading.Thread(target=self.loop)
        thread.daemon = True
        thread.start()

        return "🚀 Autonomous mode activated."

    def stop(self):

        self.running = False
        return "Autonomous mode stopped."

    def loop(self):

        while self.running:

            try:

                print("[Neo Autonomous] Learning cycle...")

                self.brain.handle_web_query("latest AI news")
                self.brain.handle_web_query("technology breakthroughs")

            except Exception as e:

                print("[Neo Autonomous Error]", e)

            time.sleep(300)