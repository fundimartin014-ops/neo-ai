from typing import Any, Optional

class ToolRegistry:
    """
    Provides registration and routing for core tools.
    """
    def __init__(self, brain: Any):
        self.brain = brain

    def list_tools(self) -> list:
        return [
            "memory_search",
            "web_search",
            "llm_reasoning",
            "entity_graph"
        ]

    def use(self, tool: str, query: str) -> Optional[Any]:
        if tool == "memory_search":
            return self.brain.get_memory(query)
        if tool == "web_search":
            return self.brain.handle_web(query)
        if tool == "entity_graph":
            return self.brain.try_graph_lookup(query)
        if tool == "llm_reasoning":
            return self.brain.reason(query, self.brain.build_context())
        return None