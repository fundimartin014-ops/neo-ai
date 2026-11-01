from core.memory import remember


class RLFeedback:

    def reward(self, query, answer):
        remember(query, answer, confidence=95, source="reward")

    def punish(self, query, answer):
        remember(query, "incorrect", confidence=10, source="penalty")