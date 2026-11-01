class Critic:

    def evaluate(self, step, result):

        if not result or "error" in str(result).lower():
            return False, "Step failed"

        if len(str(result)) < 20:
            return False, "Too weak"

        return True, "Good"