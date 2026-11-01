import time


class AutonomousLoop:

    def __init__(self, goal_manager, planner, executor, critic):

        self.goal_manager = goal_manager
        self.planner = planner
        self.executor = executor
        self.critic = critic

    def run_once(self):

        goals = self.goal_manager.get_active()

        for goal in goals:

            if not goal["steps"]:
                goal["steps"] = self.planner.create_plan(goal["text"])

            for step in goal["steps"]:

                result = self.executor.execute(step, goal)

                ok, feedback = self.critic.evaluate(step, result)

                print(f"[Step] {step}")
                print(f"[Result] {result}")
                print(f"[Critic] {feedback}")

                if not ok:
                    break

            goal["status"] = "completed"

        self.goal_manager.save()

    def run_forever(self, interval=10):

        print("[Neo] Autonomous loop started")

        while True:
            self.run_once()
            time.sleep(interval)