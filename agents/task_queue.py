import queue

class TaskQueue:
    def __init__(self):
        self.q: "queue.Queue" = queue.Queue()

    def add(self, task):
        self.q.put(task)

    def get(self, timeout=None):
        return self.q.get(timeout=timeout)

    def size(self) -> int:
        return self.q.qsize()

    def task_done(self):
        self.q.task_done()