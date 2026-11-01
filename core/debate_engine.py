from agents.debater_agent import DebaterAgent
from agents.critic_agent import CriticAgent

class DebateEngine:
    def __init__(self):
        self.debater = DebaterAgent()
        self.critic = CriticAgent()

    def evaluate(self, answers):
        scored = []

        for agent_name, answer in answers:
            critique = self.debater.challenge(answer)
            verdict = self.critic.think(answer)

            score = 0
            if critique == "Answer is strong":
                score += 1
            if verdict == "Answer acceptable":
                score += 1

            scored.append((score, answer, agent_name, critique))

        scored.sort(reverse=True)
        return scored
