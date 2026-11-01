import json
import urllib.request
from typing import Any, Dict, Optional
from agents.base_agent import BaseAgent
from agents.config import Config

class APIAgent(BaseAgent):
    name = "APIAgent"
    capabilities = ("http",)

    def __init__(self, base_url: str = None, token: str = None, **kw):
        super().__init__(**kw)
        self.base_url = base_url or Config.API_AGENT_BASE_URL
        self.api_token = token if token is not None else Config.API_AGENT_TOKEN

    def _request(self, method: str, path: str, body: dict = None) -> str:
        if not self.api_token:
            return "Error: API token not set in environment."
        if not self.base_url:
            return "Error: API_AGENT_BASE_URL not configured."
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method.upper())
        req.add_header("Authorization", f"Bearer {self.api_token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=Config.API_AGENT_TIMEOUT) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            return f"[api error] {e}"

    def run(self, request_input: Dict[str, Any]) -> str:
        method = request_input.get("method", "GET")
        path = request_input.get("path", "")
        body = request_input.get("body")
        return self._request(method, path, body)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "get":
            return self._request("GET", args[0])
        if command == "post":
            return self._request("POST", args[0], args[1] if len(args) > 1 else None)
        return f"APIAgent - command '{command}' not implemented."