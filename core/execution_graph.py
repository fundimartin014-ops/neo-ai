import threading

class ExecutionGraph:

    def __init__(self):
        self.nodes = {}
        self.results = {}

    def add_node(self, name, func):
        self.nodes[name] = func

    def run_node(self, name, func):
        try:
            self.results[name] = func()
        except Exception as e:
            self.results[name] = f"Error: {e}"

    def run(self):

        threads = []

        for name, func in self.nodes.items():
            t = threading.Thread(target=self.run_node, args=(name, func))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        return self.results