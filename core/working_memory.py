class WorkingMemory:

    def __init__(self):
        self.memory = []

    def add(self, step, result):
        self.memory.append({"step": step, "result": str(result)[:500]})

    def get_context(self):
        return "\n".join(
            f"{m['step']} → {m['result']}"
            for m in self.memory
        )

    def clear(self):
        self.memory = []