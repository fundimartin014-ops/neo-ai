import re
from core.memory import remember

class AutonomousEngine:

    def __init__(self, llm):
        self.llm = llm

    def learn_from_answer(self, question, answer):

        prompt = f"""
Extract a structured fact.

Question:
{question}

Answer:
{answer}

Return format:

entity:
attribute:
value:
"""

        response = self.llm.generate(prompt)

        entity = None
        attribute = None
        value = None

        for line in response.split("\n"):

            if line.lower().startswith("entity"):
                entity = line.split(":")[1].strip()

            if line.lower().startswith("attribute"):
                attribute = line.split(":")[1].strip()

            if line.lower().startswith("value"):
                value = line.split(":")[1].strip()

        if entity and attribute and value:

            remember(
                input_text=question,
                response=answer,
                source="autonomous_learning",
                meta={
                    "entity": entity,
                    "attribute": attribute,
                    "value": value
                },
                confidence=95
            )

            return True

        return False