class IntentClassifier:

    def classify(self, text):

        if any(word in text for word in ["current", "today", "latest"]):
            return "real_time"

        if text.startswith(("who", "what", "where", "when")):
            return "fact_lookup"

        return "general"