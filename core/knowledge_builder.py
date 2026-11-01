# core/knowledge_builder.py

import re

class KnowledgeBuilder:

    def __init__(self, brain):
        self.brain = brain

    # =====================================================
    # MAIN ENTRY
    # =====================================================
    def extract(self, query, answer):

        if not answer or len(answer.split()) > 12:
            return None

        # Try pattern extraction first (fast + reliable)
        triple = self.rule_based_extract(query, answer)

        if triple:
            return triple

        # Fallback → LLM extraction
        if self.brain.mini_llm:
            return self.llm_extract(query, answer)

        return None

    # =====================================================
    # RULE-BASED EXTRACTION
    # =====================================================
    def rule_based_extract(self, query, answer):

        q = query.lower()

        if "president" in q:
            return {
                "entity": self.extract_country(q),
                "attribute": "president",
                "value": answer
            }

        if "capital" in q:
            return {
                "entity": self.extract_country(q),
                "attribute": "capital",
                "value": answer
            }

        return None

    def extract_country(self, text):

        for c in ["kenya", "tanzania", "uganda"]:
            if c in text:
                return c.capitalize()

        return "Unknown"

    # =====================================================
    # LLM EXTRACTION (SMART)
    # =====================================================
    def llm_extract(self, query, answer):

        prompt = f"""
Extract structured fact:

Q: {query}
A: {answer}

Return ONLY JSON:
{{
 "entity": "",
 "attribute": "",
 "value": ""
}}
"""

        try:
            out = self.brain.mini_llm.generate(prompt)

            import json
            data = json.loads(out)

            if all(k in data for k in ["entity","attribute","value"]):
                return data

        except:
            pass

        return None