# ============================================
# core/verifier.py
# NEO TRUTH ENGINE V7
# ============================================

import re


class Verifier:

    def __init__(self):

        self.source_weights = {

            "memory": 1.35,
            "semantic": 1.15,
            "tool": 1.00,
            "web": 1.25,
            "llm": 0.70,
            "human_correction": 2.00
        }

    # ============================================
    # MAIN VERIFY
    # ============================================
    def verify(self, candidates):

        if not candidates:
            return None

        scored = []

        for source, text, conf in candidates:

            if not text:
                continue

            text = str(text).strip()

            if len(text) < 3:
                continue

            score = self.score_text(
                text,
                source,
                conf
            )

            scored.append({
                "text": text,
                "score": score,
                "source": source
            })

        if not scored:
            return None

        # sort highest first
        scored.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        best = scored[0]

        # reject weak hallucinations
        if best["score"] < 0.40:
            return (
                "I cannot verify that information confidently."
            )

        return best["text"]

    # ============================================
    # SCORING ENGINE
    # ============================================
    def score_text(self, text, source, conf):

        score = conf

        # source trust
        score *= self.source_weights.get(
            source,
            0.50
        )

        lower = text.lower()

        # ========================================
        # PENALTIES
        # ========================================

        # weird unicode
        if re.search(r"[^\x00-\x7F]", text):
            score *= 0.15

        # too short
        if len(text) < 12:
            score *= 0.50

        # giant spam
        if len(text.split()) > 120:
            score *= 0.70

        # repetitive garbage
        repeated = lower.count("the")

        if repeated > 25:
            score *= 0.60

        # AI disclaimer junk
        bad_patterns = [

            "as an ai",
            "i cannot browse",
            "i do not have access",
            "lorem ipsum",
            "undefined",
            "null",
            "placeholder",
            "dummy data"
        ]

        for b in bad_patterns:

            if b in lower:
                score *= 0.45

        # symbol spam
        if re.search(r"[@#$%^&*_=+<>]{4,}", text):
            score *= 0.40

        # debug contamination
        if "debug" in lower:
            score *= 0.40

        # incomplete sentence
        if len(text.split()) < 4:
            score *= 0.75

        # random ALL CAPS
        caps = sum(1 for c in text if c.isupper())

        if caps > 80:
            score *= 0.60

        # ========================================
        # BONUSES
        # ========================================

        # human verified
        if source == "human_correction":
            score *= 1.50

        # factual structure
        factual_words = [

            "president",
            "capital",
            "country",
            "founded",
            "born",
            "located",
            "official",
            "current"
        ]

        for w in factual_words:

            if w in lower:
                score *= 1.03

        return score