class AgentExecutor:

    def __init__(self, tools, llm=None):
        self.tools = tools
        self.llm = llm

    def execute(self, step):

        # 🔥 TOOL DECISION
        if "search" in step:
            func = self.tools.get("web_search")
            if func:
                return func(step)

        if self.llm:
            return self.llm.generate(f"Execute step:\n{step}")

        return None