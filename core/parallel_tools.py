from concurrent.futures import ThreadPoolExecutor


class ParallelToolExecutor:
    def __init__(self, brain):
        self.brain = brain

    def run(self, query, context=""):
        jobs = {
            "graph": lambda: self.brain.try_graph_lookup(query),
            "memory": lambda: self.brain.get_memory(query),
            "browser": lambda: self.brain.browser.research(query),
            "llm": lambda: self.brain.reason(query, context) if self.brain.mini_llm else None,
        }

        results = []

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {name: ex.submit(fn) for name, fn in jobs.items()}

            for name, fut in futures.items():
                try:
                    out = fut.result(timeout=20)
                except Exception:
                    out = None

                if not out:
                    continue

                results.extend(self._normalize(name, out))

        return results

    def _normalize(self, source, out):
        items = []

        if source == "memory" and isinstance(out, list):
            for x in out[:5]:
                text = x.get("response")
                if text:
                    items.append((x.get("source", "memory"), text, float(x.get("confidence", 0.7))))
            return items

        if source == "browser" and isinstance(out, dict):
            text = out.get("text")
            if text:
                items.append((out.get("source", "browser"), text, float(out.get("confidence", 0.8))))
            return items

        if isinstance(out, str):
            items.append((source, out, 0.6 if source == "llm" else 0.9))
            return items

        return items