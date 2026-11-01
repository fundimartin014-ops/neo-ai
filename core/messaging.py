import queue

class MessageBus:

    def __init__(self):
        self.channels = {}

    def subscribe(self, name):
        q = queue.Queue()
        self.channels[name] = q
        return q

    def send(self, target, message):
        if target in self.channels:
            self.channels[target].put(message)

    def broadcast(self, message):
        for q in self.channels.values():
            q.put(message)