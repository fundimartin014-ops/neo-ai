import time

class DeepThinker:

    def __init__(self, llm=None):
        self.llm = llm

    def think(self, goal, context="", depth=3):

        thoughts = []
        current = goal

        for i in range(depth):

            prompt = f"""
You are an advanced reasoning AI.

Goal: {goal}
Context: {context}

Step {i+1}:
- Break down the goal
- Identify risks
- Suggest next action

Answer concisely.
"""

            try:
                response = self.llm.generate(prompt) if self.llm else None
            except:
                response = None

            if not response:
                break

            thoughts.append(response)
            current = response

        return thoughts

    def decide(self, thoughts):

        if not thoughts:
            return None

        # last thought = best refined reasoning
        return thoughts[-1]