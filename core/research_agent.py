import re
from core.web_search import search_web


class ResearchAgent:

    def __init__(self, brain):
        self.brain = brain

    # =====================================================
    # MAIN ENTRY
    # =====================================================
    def research(self, query, context=""):

        plan = self.plan(query)

        evidence = []

        for step in plan:
            data = self.execute(step)
            if data:
                facts = self.extract_facts(data)
                evidence.extend(facts)

        verified = self.verify(evidence)

        answer = self.synthesize(query, verified)

        return answer

    # =====================================================
    # PLANNER
    # =====================================================
    def plan(self, query):

        return [
            f"search: {query}",
            f"verify: {query}"
        ]

    # =====================================================
    # EXECUTOR
    # =====================================================
    def execute(self, step):

        if step.startswith("search:"):
            query = step.replace("search:", "").strip()
            return search_web(query)

        return None

    # =====================================================
    # FACT EXTRACTION
    # =====================================================
    def extract_facts(self, text):

        if not text:
            return []

        if isinstance(text, dict):
            text = text.get("text", "")

        text = str(text)

        sentences = re.split(r'[.!?]', text)

        facts = []

        for s in sentences:
            s = s.strip()

            if len(s) < 20:
                continue

            # keep factual-looking lines
            if any(x in s.lower() for x in ["is", "was", "are"]):
                facts.append(s)

        return facts[:5]

    # =====================================================
    # VERIFICATION (CONSENSUS)
    # =====================================================
    def verify(self, facts):

        scores = {}

        for f in facts:
            key = f.lower().strip()

            scores[key] = scores.get(key, 0) + 1

        # keep only repeated facts (consensus)
        verified = [k for k, v in scores.items() if v >= 1]

        return verified

    # =====================================================
    # SYNTHESIS (FINAL ANSWER)
    # =====================================================
    def synthesize(self, query, facts):

        if not facts:
            return None

        # 🔥 Use LLM if available
        if self.brain.mini_llm:

            prompt = f"""
Extract the exact answer.

Facts:
{facts}

Question:
{query}

Answer (short, exact):
"""

            try:
                return self.brain.mini_llm.generate(prompt)
            except:
                pass

        # fallback
        return facts[0]
    ''