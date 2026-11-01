from collections import defaultdict
from core.memory import _load_memory


class EntityGraph:
    def __init__(self):
        self.graph = defaultdict(lambda: defaultdict(list))
        self.relations = defaultdict(list)
        self.build_graph()

    def build_graph(self):
        self.graph.clear()
        self.relations.clear()

        memory = _load_memory()

        for item in memory:
            meta = item.get("meta", {})
            entity = meta.get("entity")
            attribute = meta.get("attribute")
            value = meta.get("value")

            if entity and attribute and value:
                fact = {
                    "value": value,
                    "confidence": item.get("confidence", 50),
                    "source": item.get("source", "unknown"),
                    "timestamp": item.get("timestamp", 0),
                    "start_time": meta.get("start_time"),
                    "end_time": meta.get("end_time")
                }

                self.graph[entity][attribute].append(fact)

                if isinstance(value, str) and value.istitle():
                    self.relations[entity].append({
                        "type": attribute,
                        "target": value,
                        "confidence": fact["confidence"]
                    })

    def refresh(self):
        self.build_graph()

    def get_best_fact(self, entity, attribute):
        facts = self.graph.get(entity, {}).get(attribute, [])
        if not facts:
            return None

        facts.sort(
            key=lambda x: (x.get("confidence", 0), x.get("timestamp", 0)),
            reverse=True
        )
        return facts[0]

    def get_fact_at_time(self, entity, attribute, year):
        facts = self.graph.get(entity, {}).get(attribute, [])
        for f in facts:
            start = f.get("start_time")
            end = f.get("end_time")
            if start and end and start <= year <= end:
                return f
        return None

    def detect_conflicts(self, entity, attribute):
        facts = self.graph.get(entity, {}).get(attribute, [])
        if len(facts) < 2:
            return None

        weighted = {}
        for f in facts:
            val = f.get("value")
            conf = f.get("confidence", 0)
            weighted[val] = weighted.get(val, 0) + conf

        if len(weighted) > 1:
            return {
                "entity": entity,
                "attribute": attribute,
                "candidates": weighted
            }
        return None

    def get_relations(self, entity):
        return self.relations.get(entity, [])