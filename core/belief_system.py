import time


class BeliefSystem:

    def __init__(self):
        self.beliefs = {}  # {question: {answer, confidence, timestamp}}

    def update(self, question, answer, confidence):

        now = time.time()

        if question not in self.beliefs:
            self.beliefs[question] = {
                "answer": answer,
                "confidence": confidence,
                "timestamp": now
            }
            return

        existing = self.beliefs[question]

        # 🔥 if new answer stronger → replace
        if confidence > existing["confidence"]:
            self.beliefs[question] = {
                "answer": answer,
                "confidence": confidence,
                "timestamp": now
            }

        # 🔥 if same answer → reinforce
        elif answer == existing["answer"]:
            existing["confidence"] += 0.1
            existing["timestamp"] = now

        # 🔥 if contradiction → decay old belief
        else:
            existing["confidence"] *= 0.7

    def get(self, question):

        if question not in self.beliefs:
            return None

        belief = self.beliefs[question]

        # 🔥 time decay
        age = time.time() - belief["timestamp"]

        if age > 86400:  # 1 day
            belief["confidence"] *= 0.9

        return belief["answer"]