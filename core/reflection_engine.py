class ReflectionEngine:

    def evaluate(self, result):

        if not result:
            return False

        if len(str(result)) < 10:
            return False

        return True