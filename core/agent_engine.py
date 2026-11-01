class AgentEngine:

    def __init__(self, brain):
        self.brain = brain

    # =====================================================
    # MAIN AGENT LOOP
    # =====================================================
    def run(self, query, context=""):

        steps = self.plan(query)

        all_results = []

        for step in steps:
            results = self.execute(step, context)
            all_results.extend(results)

        best = self.critic(all_results)

        if not best:
            best = self.reflect(query, context)

        return best

    # =====================================================
    # PLANNER
    # =====================================================
    def plan(self, query):

        llm = self.brain.mini_llm

        if not llm:
            return [query]

        prompt = f"""
Break into steps:

Task: {query}

Steps:
"""

        try:
            steps = llm.generate(prompt)
            return [s.strip("- ").strip() for s in steps.split("\n") if s.strip()]
        except:
            return [query]

    # =====================================================
    # EXECUTOR (TOOLS)
    # =====================================================
    def execute(self, step, context):

        results = []

        # GRAPH
        g = self.brain.try_graph_lookup(step)
        if g:
            results.append(("graph", g, 0.95))

        # MEMORY
        mem = self.brain.get_memory(step)
        if mem:
            results.append(("memory", mem, 0.8))

        # WEB
        web = self.brain.handle_web(step)
        if web:
            results.append(("web", web, 0.75))

        # LLM
        if self.brain.mini_llm:
            llm = self.brain.reason(step, context)
            if llm:
                results.append(("llm", llm, 0.6))

        return results

    # =====================================================
    # CRITIC (TRUTH ENGINE)
    # =====================================================
    def critic(self, candidates):

        if not candidates:
            return None

        scores = {}

        for source, text, conf in candidates:

            key = text.strip().lower()

            weight = {
                "graph": 1.0,
                "memory": 0.9,
                "web": 0.85,
                "llm": 0.5
            }.get(source, 0.5)

            scores[key] = scores.get(key, 0) + (conf * weight)

        best, score = max(scores.items(), key=lambda x: x[1])

        # contradiction detection
        conflicts = [k for k in scores if k != best and scores[k] > score * 0.7]

        if conflicts:
            return self.resolve(best, conflicts)

        return best

    # =====================================================
    # RESOLVE CONFLICT
    # =====================================================
    def resolve(self, best, others):

        best_len = len(best.split())

        for alt in others:
            if len(alt.split()) < best_len:
                best = alt

        return best

    # =====================================================
    # REFLECTION LOOP
    # =====================================================
    def reflect(self, query, context):

        llm = self.brain.mini_llm

        if not llm:
            return None

        prompt = f"""
Previous answer may be wrong.

Question: {query}

Think again carefully.

Answer:
"""

        try:
            return llm.generate(prompt)
        except:
            return None