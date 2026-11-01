class Executor:

    def __init__(self, brain):
        self.brain = brain

    def execute(self, step, goal):

        if "search" in step:
            return self.brain.handle_browser(goal["text"])

        if "extract" in step:
            return "Extracted key points."

        if "summarize" in step:
            return "Summary created."

        return f"Executed: {step}"