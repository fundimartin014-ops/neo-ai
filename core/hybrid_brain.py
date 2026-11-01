from core.memory import search_knowledge
from core.web_search import search_web

class HybridBrain:

    def __init__(self, entity_graph, llm):
        self.entity_graph = entity_graph
        self.llm = llm

    def collect_graph_knowledge(self, query):

        results = []

        for entity in self.entity_graph.graph:

            if entity.lower() in query.lower():

                for attr in self.entity_graph.graph[entity]:

                    best = self.entity_graph.get_best_fact(entity, attr)

                    if best:
                        results.append(
                            f"{entity} {attr}: {best['value']}"
                        )

        return "\n".join(results)

    def collect_memory(self, query):

        memory = search_knowledge(query)

        if not memory:
            return ""

        return "\n".join(
            [m["response"] for m in memory[:3]]
        )

    def collect_web(self, query):

        web = search_web(query)

        if isinstance(web, dict) and "text" in web:

            return web["text"][:1500]

        return ""

    def build_context(self, query):

        graph_data = self.collect_graph_knowledge(query)

        memory_data = self.collect_memory(query)

        web_data = self.collect_web(query)

        context = f"""
GRAPH KNOWLEDGE:
{graph_data}

MEMORY KNOWLEDGE:
{memory_data}

WEB DATA:
{web_data}
"""

        return context

    def reason(self, query):

        context = self.build_context(query)

        prompt = f"""
You are Neo, an intelligent assistant.

Use the knowledge below to answer the question.

{context}

QUESTION:
{query}

Give a clear factual answer.
"""

        return self.llm.generate(prompt)