class SelfReflection:

    def evaluate(self, answer):

        score = 0

        if len(answer) > 50:
            score += 1

        if "." in answer:
            score += 1

        if "I don't know" not in answer:
            score += 1

        return {
            "score": score,
            "quality": "good" if score >=2 else "weak"
        }