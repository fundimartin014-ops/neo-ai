import re
from core.memory import remember

class KnowledgeExtractor:

    def extract(self, text):

        relations = []

        # PRESIDENT
        match = re.search(r"(.*?) is the president of (.*?)[\.\n]", text, re.I)
        if match:
            person = match.group(1).strip()
            country = match.group(2).strip()

            relations.append({
                "entity": country,
                "attribute": "president",
                "value": person
            })

        # DEPUTY PRESIDENT
        match = re.search(r"(.*?) is the deputy president of (.*?)[\.\n]", text, re.I)
        if match:
            person = match.group(1).strip()
            country = match.group(2).strip()

            relations.append({
                "entity": country,
                "attribute": "deputy president",
                "value": person
            })

        return relations


    def store(self, relations):

        for r in relations:

            remember(
                input_text=f"{r['entity']} {r['attribute']}",
                response=f"{r['value']}",
                source="auto_extracted",
                meta={
                    "entity": r["entity"],
                    "attribute": r["attribute"],
                    "value": r["value"]
                },
                confidence=90
            )