import requests
from bs4 import BeautifulSoup
from core.memory import remember


class URLLearner:

    def fetch(self, url):

        try:
            res = requests.get(url, timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")

            paragraphs = [p.get_text() for p in soup.find_all("p")]

            text = " ".join(paragraphs[:20])

            return text

        except:
            return None

    def learn(self, url):

        text = self.fetch(url)

        if not text or len(text) < 50:
            return "Failed to extract useful content."

        # chunk
        chunks = [text[i:i+500] for i in range(0, len(text), 500)]

        for chunk in chunks:
            remember(
                input_text=url,
                response=chunk,
                source="web"
            )

        return f"Learned from {url} ({len(chunks)} chunks)"