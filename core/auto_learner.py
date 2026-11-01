import time
from core.web_search import search_web
from core.memory import remember


class AutoLearner:

    def __init__(self, brain):
        self.brain = brain
        self.queue = []
        self.running = True

    # =====================================================
    # ADD UNKNOWN QUERY
    # =====================================================

    def add_task(self, query):
        if query not in self.queue:
            print(f"[AutoLearn] Queued: {query}")
            self.queue.append(query)

    # =====================================================
    # BACKGROUND LOOP
    # =====================================================

    def run(self):

        print("[AutoLearn] Autonomous learning started")

        while self.running:

            if not self.queue:
                time.sleep(2)
                continue

            query = self.queue.pop(0)

            try:
                print(f"[AutoLearn] Learning: {query}")

                web = search_web(query)

                if not web:
                    continue

                text = web.get("text") if isinstance(web, dict) else str(web)

                if not text:
                    continue

                # 🧠 USE LLM TO EXTRACT FACT
                if self.brain.mini_llm:

                    prompt = f"""
Extract the exact answer.

Q: {query}

From:
{text[:800]}

Rules:
- max 6 words
- no explanation

Answer:
"""

                    answer = self.brain.mini_llm.generate(prompt)

                    if answer and self.brain.valid(answer):

                        remember(
                            input_text=query,
                            response=answer,
                            source="auto_learned",
                            confidence=85
                        )

                        print(f"[AutoLearn] Learned: {query} → {answer}")

            except Exception as e:
                print("[AutoLearn Error]", e)

            time.sleep(1)