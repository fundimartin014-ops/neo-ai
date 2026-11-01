# core/github_client.py
import requests
import time

class GitHubClient:
    def __init__(self, token=None):
        self.token = token
        self.base = "https://api.github.com"
        self.last_call = 0
        
    def _get(self, endpoint, params=None):
        # Rate limit safety: 1 req/sec max
        now = time.time()
        if now - self.last_call < 1:
            time.sleep(1 - (now - self.last_call))
        self.last_call = time.time()
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
            
        r = requests.get(f"{self.base}{endpoint}", headers=headers, params=params, timeout=10)
        
        if r.status_code == 403:
            return {"error": "Rate limit hit. Wait 1 hour or add GITHUB_TOKEN."}
        if r.status_code == 404:
            return {"error": "Not found."}
            
        r.raise_for_status()
        return r.json()
        
    def get_user_repos(self, username):
        data = self._get(f"/users/{username}/repos", params={"sort": "updated", "per_page": 5})
        if isinstance(data, dict) and "error" in data:
            return data["error"]
        return [f"{r['name']} (⭐{r['stargazers_count']})" for r in data]
        
    def get_repo_readme(self, owner, repo):
        data = self._get(f"/repos/{owner}/{repo}/readme")
        if isinstance(data, dict) and "error" in data:
            return data["error"]
        import base64
        return base64.b64decode(data["content"]).decode("utf-8")[:2000]