class Critic:

    def __init__(self, brain):
        self.brain = brain

    def validate(self, query, answers):

        text = str(answers)

        prompt = f"""
Multiple answers found:

{answers}

Which is most factual?

Return ONLY best answer.
"""

        try:
            return self.brain.mini_llm.generate(prompt)
        except:
            return None