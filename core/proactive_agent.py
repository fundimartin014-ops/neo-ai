import time
from core.web_search import search_web
from core.memory import remember


TRUSTED_TOPICS = [
    "kenya politics",
    "world news",
    "technology ai",
    "agriculture farming",
    "weather kenya"
]


class ProactiveAgent:

    def __init__(self, brain):
        self.brain = brain
        self.running = True
        self.interval = 60  # seconds between learning cycles

    # =====================================================
    # MAIN LOOP
    # =====================================================

    def run(self):

        print("[Proactive] Intelligence loop started")

        while self.running:

            for topic in TRUSTED_TOPICS:

                try:
                    print(f"[Proactive] Scanning: {topic}")

                    result = search_web(topic)

                    if not result:
                        continue

                    text = result.get("text") if isinstance(result, dict) else str(result)

                    if not text or len(text) < 50:
                        continue

                    # 🧠 EXTRACT FACTS USING LLM
                    if self.brain.mini_llm:

                        prompt = f"""
Extract 3 important facts.

From:
{text[:1000]}

Rules:
- each fact max 8 words
- no explanation
- clean facts only

Facts:
"""

                        facts = self.brain.mini_llm.generate(prompt)

                        if not facts:
                            continue

                        lines = facts.split("\n")

                        for fact in lines:

                            fact = fact.strip("- ").strip()

                            if not self.brain.valid(fact):
                                continue

                            if len(fact.split()) > 8:
                                continue

                            remember(
                                input_text=topic,
                                response=fact,
                                source="proactive",
                                confidence=70
                            )

                            print(f"[Proactive] Learned: {fact}")

                except Exception as e:
                    print("[Proactive Error]", e)

            time.sleep(self.interval)