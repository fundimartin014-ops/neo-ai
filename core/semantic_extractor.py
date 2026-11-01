class SemanticExtractor:

    def __init__(self, llm):
        self.llm = llm

    def extract(self, query, summary):
        prompt = f"""
You are an information extraction engine.

From the query and summary below, extract:

1. entity (country, person, organization)
2. attribute (role or property being asked)
3. value (answer)

Return strictly in this JSON format:

{{
  "entity": "...",
  "attribute": "...",
  "value": "..."
}}

Query:
{query}

Summary:
{summary}
"""

        response = self.llm.generate(prompt)

        try:
            import json
            return json.loads(response)
        except:
            return None