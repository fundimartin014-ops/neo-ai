class SessionMemory:
    def __init__(self):
        self.last_topic = None
        self.last_source = None

    def update(self, topic=None, source=None):
        if topic:
            self.last_topic = topic
        if source:
            self.last_source = source
