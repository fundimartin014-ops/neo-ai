class SwarmCoordinator:

    def __init__(self, brain=None):

        self.brain = brain

        self.agents = {
            "planner": self.planner_agent,
            "researcher": self.research_agent,
            "reasoner": self.reason_agent,
            "critic": self.critic_agent,
            "memory": self.memory_agent
        }

    def run(self, query):

        plan = self.agents["planner"](query)

        research = self.agents["researcher"](query)

        answer = self.agents["reasoner"](query, research)

        review = self.agents["critic"](answer)

        self.agents["memory"](query, answer)

        return answer

    def handle(self, query):
        return self.run(query)

    # ---- AGENTS ----

    def planner_agent(self, query):

        return f"Plan created for: {query}"

    def research_agent(self, query):

        try:
            if not self.brain:
                return None
            web = self.brain.handle_web_query(query)
            return web
        except:
            return None

    def reason_agent(self, query, context):

        if self.brain and self.brain.mini_llm:

            prompt = f"""
Use the information below to answer clearly.

Context:
{context}

Question:
{query}
"""

            return self.brain.mini_llm.generate(prompt)

        return "No reasoning engine available."

    def critic_agent(self, answer):

        if len(answer) < 40:
            return "weak"

        return "good"

    def memory_agent(self, query, answer):

        try:
            from core.semantic_memory import store
            store(query, answer)
        except:
            pass
