import re

class AgentLoop:

    def __init__(self, brain):
        self.brain = brain
        self.max_steps = 3

    # =====================================
    # MAIN AGENT EXECUTION
    # =====================================

    def run(self, query):

        context = ""
        history = []

        for step in range(self.max_steps):

            print(f"[Agent] Step {step+1}")

            # PLAN
            action = self.plan(query, context)

            print(f"[Agent] Plan → {action}")

            # ACT
            result = self.act(action, query)

            print(f"[Agent] Result → {result}")

            history.append((action, result))

            # CHECK QUALITY
            if self.is_good_answer(result):
                return result

            # REFLECT (improve next step)
            context += f"\nStep {step+1}: {result}"

        return result  # fallback

    # =====================================
    # PLAN (LLM decides next move)
    # =====================================

    def plan(self, query, context):

        if not self.brain.mini_llm:
            return "web"

        prompt = f"""
You are an AI planner.

Decide the best next action.

Available actions:
- graph (for known facts)
- memory (for learned info)
- web (for new info)
- answer (if you already know)

Context:
{context}

Question:
{query}

Reply with ONE word:
"""

        try:
            action = self.brain.mini_llm.generate(prompt).lower().strip()
            return action
        except:
            return "web"

    # =====================================
    # ACT (execute tool)
    # =====================================

    def act(self, action, query):

        if action == "graph":
            return self.brain.try_graph_lookup(query)

        if action == "memory":
            return self.brain.get_memory(query)

        if action == "web":
            return self.brain.handle_web(query)

        if action == "answer":
            return self.brain.reason(query)

        return None

    # =====================================
    # VALIDATION
    # =====================================

    def is_good_answer(self, text):

        if not text:
            return False

        t = text.lower()

        # reject garbage
        bad = ["pdf", "training", "here", "found"]

        if any(b in t for b in bad):
            return False

        if len(text.split()) > 30:
            return False

        return True