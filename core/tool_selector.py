class ToolSelector:

    def select_tools(self, query):

        q = query.lower()

        if "http" in q or "www" in q:
            return ["browser_open"]

        if "search" in q or "find" in q:
            return ["browser_search"]

        if "explain" in q or "why" in q:
            return ["llm_reason"]

        return ["web_search"]