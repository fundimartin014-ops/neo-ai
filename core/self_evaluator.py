from core.memory import search_knowledge

class SelfEvaluator:

    def evaluate_answer(self, query, response):
        score = 0

        if len(response) > 50:
            score += 10

        if any(word in response.lower() for word in query.lower().split()):
            score += 10

        memory_hits = search_knowledge(query)
        if memory_hits:
            score += 15

        return score

    def needs_improvement(self, score):
        return score < 20