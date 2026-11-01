class ToolLearning:

    def __init__(self):
        self.stats = {}

    def record(self, tool, success):

        if tool not in self.stats:
            self.stats[tool] = {"success": 0, "fail": 0}

        if success:
            self.stats[tool]["success"] += 1
        else:
            self.stats[tool]["fail"] += 1

    def score(self, tool):

        s = self.stats.get(tool, {"success": 1, "fail": 1})
        return s["success"] / (s["success"] + s["fail"])

    def best_tools(self):
        return sorted(self.stats, key=lambda t: self.score(t), reverse=True)