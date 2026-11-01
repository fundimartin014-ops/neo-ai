import re
from core.web_search import search_web


class KnowledgeEngine:

    def __init__(self, brain):
        self.brain = brain

    # =====================================================
    # MAIN VERIFIED QUERY
    # =====================================================
    def get_verified_answer(self, query):

        facts = []

        # 🔥 1. Wikipedia-style query
        wiki_data = self.get_wikipedia(query)
        if wiki_data:
            facts.extend(self.extract_structured(wiki_data, source="wiki"))

        # 🔥 2. Multi-source web
        web_data = search_web(query)
        if web_data:
            facts.extend(self.extract_structured(web_data, source="web"))

        # 🔥 3. Validate facts
        verified = self.verify_facts(facts)

        # 🔥 4. Select best
        return self.select_best_fact(verified)

    # =====================================================
    # WIKIPEDIA FETCH (SIMPLE)
    # =====================================================
    def get_wikipedia(self, query):

        data = search_web(f"{query} wikipedia")

        if isinstance(data, dict):
            return data.get("text", "")

        return str(data)

    # =====================================================
    # STRUCTURED EXTRACTION
    # =====================================================
    def extract_structured(self, text, source="web"):

        if not text:
            return []

        text = str(text)

        sentences = re.split(r'[.!?]', text)

        facts = []

        for s in sentences:

            s = s.strip()
            if len(s) < 20:
                continue

            # 🔥 detect "X is Y"
            match = re.search(r"(.+?) is (.+)", s)

            if match:
                entity = match.group(1).strip()
                value = match.group(2).strip()

                facts.append({
                    "entity": entity.lower(),
                    "value": value,
                    "source": source
                })

        return facts

    # =====================================================
    # VERIFY FACTS (CONSENSUS)
    # =====================================================
    def verify_facts(self, facts):

        scored = {}

        for f in facts:

            key = f["value"].lower()

            weight = {
                "wiki": 1.2,
                "web": 0.8
            }.get(f["source"], 0.5)

            scored[key] = scored.get(key, 0) + weight

        return scored

    # =====================================================
    # SELECT BEST FACT
    # =====================================================
    def select_best_fact(self, scored):

        if not scored:
            return None

        best = max(scored.items(), key=lambda x: x[1])

        return best[0]