class AgentPlanner:

    def create_plan(self, query):

        # simple decomposition (expand later with LLM if needed)
        steps = []

        if "search" in query or "find" in query:
            steps.append("search information about " + query)

        steps.append("analyze information about " + query)
        steps.append("summarize final answer")

        return steps