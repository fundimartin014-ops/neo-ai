from core.memory import search_knowledge, remember
from core.knowledge_graph import add_relation
import re


def extract_simple_facts(text):

    # Basic pattern detection
    patterns = [
        r"(.+?) is the (.+?) of (.+?)\.",
        r"(.+?) was born in (.+?)\.",
    ]

    facts = []

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            facts.append(m)

    return facts


def evolve_from_answer(answer_text):

    facts = extract_simple_facts(answer_text)

    for fact in facts:
        if len(fact) == 3:
            subject, relation, obj = fact
            add_relation(subject.strip(), relation.strip(), obj.strip())
