import logging
import os
import requests
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        # Token is OPTIONAL. Unauthenticated = 60 req/hour.
        self.token = os.getenv("GITHUB_TOKEN")
        self.base = "https://api.github.com"
        self.last_call = 0
        mode = "authenticated" if self.token else "unauthenticated (60 req/hour)"
        logger.info(f"[GitHub] Plugin initialized. Mode: {mode}")

    def run(self):
        logger.info("GitHub plugin ready. Use search_repos() or get_repo().")

    def _get(self, endpoint, params=None):
        # Rate-limit safety: 1 req/sec max
        now = time.time()
        if now - self.last_call < 1:
            time.sleep(1 - (now - self.last_call))
        self.last_call = now

        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        r = requests.get(f"{self.base}{endpoint}", headers=headers, params=params, timeout=10)
        if r.status_code == 403:
            return {"error": "GitHub rate limit hit. Add GITHUB_TOKEN to .env or wait 1 hour."}
        if r.status_code == 404:
            return {"error": "Not found."}
        r.raise_for_status()
        return r.json()

    def search_repos(self, query, per_page=3):
        data = self._get("/search/repositories", params={"q": query, "per_page": per_page})
        if isinstance(data, dict) and "error" in data:
            return data["error"]
        items = data.get("items", [])
        return [f"{i['full_name']} (⭐{i['stargazers_count']})" for i in items]

    def get_repo(self, owner, repo):
        data = self._get(f"/repos/{owner}/{repo}")
        if isinstance(data, dict) and "error" in data:
            return data["error"]
        return f"⭐ {data['stargazers_count']} | 🍴 {data['forks_count']} | {data['description'] or 'No description'}"