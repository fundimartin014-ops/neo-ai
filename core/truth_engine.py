import re
from collections import defaultdict
from core.source_ranker import rank_source


class TruthEngine:

    def decide(self, candidates):

        if not candidates:
            return None, 0

        grouped = self.group(candidates)

        best_text = None
        best_score = 0

        for key, items in grouped.items():

            score = self.score(items)

            if score > best_score:
                best_score = score
                best_text = items[0][1]

        return best_text, best_score

    def group(self, candidates):

        groups = []

        for source, text, conf in candidates:

            norm = self.normalize(text)

            placed = False

            for g in groups:
                if self.similar(norm, g["rep"]):
                    g["items"].append((source, text, conf))
                    placed = True
                    break

            if not placed:
                groups.append({
                    "rep": norm,
                    "items": [(source, text, conf)]
                })

        return {g["rep"]: g["items"] for g in groups}

    def score(self, items):

        score = 0
        sources = set()

        for source, text, conf in items:

            weight = {
                "memory": 1.5,
                "semantic": 1.2,
                "web": 1.3,
                "tool": 1.0,
                "llm": 0.3
            }.get(source, 0.5)

            source_bonus = rank_source(text)

            score += conf * weight * source_bonus
            sources.add(source)

            if len(text) < 15:
                score *= 0.7

            if re.search(r"[^\x00-\x7F]", text):
                score *= 0.3

        # consensus
        score += len(items) * 0.6

        # diversity
        score += len(sources) * 0.4

        return score

    def normalize(self, text):
        return re.sub(r'\W+', ' ', text.lower()).strip()

    def similar(self, a, b):
        return a in b or b in a