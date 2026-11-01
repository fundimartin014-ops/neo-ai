import time

class AutoTrainer:

    def __init__(self, brain):
        self.brain = brain

    def run(self):
        print("[AutoTrainer] Running background learning...")

        while True:
            try:
                self.learn_cycle()
                time.sleep(300)  # every 5 min
            except:
                pass

    def learn_cycle(self):

        topics = [
            "current president of kenya",
            "ai technology",
            "latest news africa"
        ]

        for t in topics:
            result = self.brain.handle_web(t)

            if result:
                self.brain.learn(t, result)
                print(f"[AutoTrainer] Learned: {t}")