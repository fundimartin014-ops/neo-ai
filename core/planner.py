"""
core/planner.py
Stub to resolve import conflicts. 
The real planning logic is now in core/orchestrator.py
"""


# If fundibrain imports Planner, provide a compatible stub
class Planner:
    """Legacy stub - planning moved to NeoOrchestrator in core/orchestrator.py"""
    def __init__(self):
        pass

    def plan(self, query: str):
        return {"intent": "unknown", "tools": []}

    # --- ADDED: compat shim for fundibrain.py autonomous loop ---
    def create_plan(self, goal: str):
        """
        Legacy signature used by fundibrain.FundiBrain._loop():
            plan = self.planner.create_plan(goal)
            for step in plan: ...
        Returns a list of step strings.
        """
        if not goal:
            return []
        import re as _re
        parts = _re.split(r"\s*(?:,\s*|;\s*|\band then\b|\bthen\b|\band\b)\s*", str(goal))
        steps = [p.strip() for p in parts if p and p.strip()]
        return steps or [str(goal)]


# --- ADDED: ReasoningPlanner expected by core/brain.py ---
class ReasoningPlanner(Planner):
    """
    Adapter for core/brain.py:
        from core.planner import ReasoningPlanner
        self.planner = ReasoningPlanner()
        plan = self.planner.create_plan(intent, entities)
    Delegates to Planner.create_plan(goal) after flattening intent+entities
    into a single goal string.
    """

    def create_plan(self, intent, entities=None):
        parts = []
        if intent:
            parts.append(str(intent))
        if entities:
            if isinstance(entities, dict):
                ent_str = ", ".join(f"{k}={v}" for k, v in entities.items())
            elif isinstance(entities, (list, tuple, set)):
                ent_str = ", ".join(str(e) for e in entities)
            else:
                ent_str = str(entities)
            parts.append("targets: " + ent_str)
        goal = " | ".join(parts) if parts else "answer the user's query"
        return super().create_plan(goal)