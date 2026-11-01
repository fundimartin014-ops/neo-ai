import json
import os
import time

class GoalManager:

    def __init__(self, file="goals.json"):

        self.file = file
        self.goals = self.load()

    def load(self):
        if os.path.exists(self.file):
            with open(self.file, "r") as f:
                return json.load(f)
        return []

    def save(self):
        with open(self.file, "w") as f:
            json.dump(self.goals, f, indent=2)

    def add_goal(self, goal):

        self.goals.append({
            "text": goal,
            "status": "pending",
            "priority": 1.0,
            "attempts": 0,
            "created": time.time()
        })

        self.save()

    def get_next_goal(self):

        active = [g for g in self.goals if g["status"] == "pending"]

        if not active:
            return None

        # 🔥 PRIORITY + AGE BOOST
        for g in active:
            age = time.time() - g["created"]
            g["score"] = g["priority"] + (age * 0.0001)

        best = sorted(active, key=lambda x: x["score"], reverse=True)[0]

        best["attempts"] += 1
        self.save()

        return best["text"]

    def complete_goal(self, goal):

        for g in self.goals:
            if g["text"] == goal:
                g["status"] = "done"

        self.save()

    def fail_goal(self, goal):

        for g in self.goals:
            if g["text"] == goal:
                g["priority"] *= 0.8

        self.save()