# core/plugins/pdf_answer_plugin.py

from core.memory import search_knowledge
from core.topic import detect_topic
import re


class Plugin:

    def can_handle(self, text):
        return True

    def handle(self, text):

        topic = detect_topic(text)
        results = search_knowledge(text)

        pdf_results = [r for r in results if r["source"] == "pdf"]

        if not pdf_results:
            return None

        combined = "\n\n".join([r["response"] for r in pdf_results[:3]])

        return self.summarize(combined)

    def summarize(self, text):

        text = " ".join(text.split())

        sentences = re.split(r'(?<=[.!?]) +', text)

        best = [s for s in sentences if len(s) > 40]

        return " ".join(best[:3])[:2000]
