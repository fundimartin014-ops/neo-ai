import re

class LinguisticProcessor:

    def process(self, text):
        text = text.lower().strip()

        fixes = {
            "whois": "who is",
            "whatis": "what is",
            "presdent": "president"
        }

        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)

        text = re.sub(r'\s+', ' ', text)

        return text