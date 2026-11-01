class ReasoningPlanner:

    def __init__(self, llm):
        self.llm = llm

    def create_plan(self, goal):

        prompt = f"""
You are an AI planner.

Break this goal into clear steps.
Each step should include:
- action
- tool (if needed)

Goal: {goal}

Return JSON list like:
[
  {{"step": "...", "tool": "..."}},
]
"""

        try:
            response = self.llm.generate(prompt)
            return eval(response)
        except:
            return [{"step": goal, "tool": None}]