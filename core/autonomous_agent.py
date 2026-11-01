class AutonomousAgent:

    def __init__(self, brain, goals, tools):
        self.brain = brain
        self.goals = goals
        self.tools = tools

    # =====================================================
    # MAIN LOOP (SAFE AUTONOMOUS EXECUTION)
    # =====================================================
    def run_cycle(self):

        active_goals = self.goals.get_active()

        if not active_goals:
            return "[Agent] No active goals."

        for goal in active_goals:

            if goal["status"] == "done":
                continue

            print(f"[Agent] Working on: {goal['task']}")

            # STEP 1: PLAN
            steps = self.plan(goal["task"])

            # STEP 2: EXECUTE
            results = []
            for step in steps:
                result = self.execute(step)
                if result:
                    results.append(result)

            # STEP 3: EVALUATE
            success = self.evaluate(goal["task"], results)

            if success:
                self.goals.update(goal["id"], {"status": "done"})
                print("[Agent] Goal completed.")
            else:
                self.goals.update(goal["id"], {
                    "steps": steps,
                    "last_results": results
                })

    # =====================================================
    # PLANNING
    # =====================================================
    def plan(self, task):

        prompt = f"""
Break task into steps using available tools.

Task: {task}

Tools: {self.tools.list_tools()}

Steps:
"""

        try:
            response = self.brain.mini_llm.generate(prompt)
            return [s.strip("- ").strip() for s in response.split("\n") if s.strip()]
        except:
            return [task]

    # =====================================================
    # EXECUTION
    # =====================================================
    def execute(self, step):

        for tool in self.tools.list_tools():
            result = self.tools.use(tool, step)

            if result:
                return result

        return None

    # =====================================================
    # EVALUATION (SELF-REFLECTION)
    # =====================================================
    def evaluate(self, task, results):

        text = " ".join(results)

        prompt = f"""
Did this solve the task?

Task: {task}
Result: {text}

Answer yes or no.
"""

        try:
            verdict = self.brain.mini_llm.generate(prompt)
            return "yes" in verdict.lower()
        except:
            return False