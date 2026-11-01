from core.web_fallback import fetch_web_answers


class WebTool:
    def search(self, entities):
        query = " ".join(entities) if isinstance(entities, list) else str(entities or "")
        answers = fetch_web_answers(query)
        return {"answer": answers[0] if answers else "No answer found."}
