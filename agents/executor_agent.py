import re
from datetime import datetime, timedelta
import threading
from typing import Any, Optional

from agents.base_agent import BaseAgent
from agents.registry import AgentRegistry
from agents.message_bus import SHUTDOWN

_URL_RE = re.compile(r"(https?://\S+|[a-z0-9.-]+\.[a-z]{2,}(?:/\S*)?)", re.I)

# LLM-friendly short name -> full registered name
AGENT_ALIASES = {
    "web": "WebAgent",
    "search": "SearchAgent",
    "farm": "FarmerDigestAgent",
    "disease": "DiseaseAlertAgent",
    "image_analysis": "ImageAnalysisAgent",
    "transcribe": "TranscriptionAgent",
    "location": "LocationAgent",
    "speak": "SpeechAgent",
    "device": "DeviceControlAgent",
    "iot": "DeviceControlAgent",
    "tts": "SpeechAgent",
    "voice": "TranscriptionAgent",
    "analyze_image": "ImageAnalysisAgent",
    "diagnose": "DiseaseAlertAgent",
    "brief": "FarmerDigestAgent",
    "summarize": "SummarizerAgent",
    "summary": "SummarizerAgent",
    "api": "APIAgent",
    "knowledge": "KnowledgeAgent",
    "file": "FileManagementAgent",
    "files": "FileManagementAgent",
    "system": "SystemAgent",
    "shell": "SystemAgent",
    "task": "TaskAgent",
    "tasks": "TaskAgent",
    "security": "SecurityAgent",
    "audit": "AuditAgent",
    "metrics": "MetricsAgent",
    "sentiment": "SentimentAgent",
    "tag": "TaggingAgent",
    "tagging": "TaggingAgent",
    "memory": "MemoryAgent",
    "session": "SessionAgent",
    "profile": "UserProfileAgent",
    "notify": "NotificationAgent",
    "notification": "NotificationAgent",
    "feedback": "FeedbackAgent",
    "conversation": "ConversationAgent",
    "chat": "ConversationAgent",
    "think": "ThinkerAgent",
    "debate": "DebaterAgent",
    "planner": "PlannerAgent",
    "validate": "InputValidationAgent",
    "validate": "InputValidationAgent",
}


_DATE_KEYS = {
    "today":     lambda n: n.strftime("%Y-%m-%d"),
    "yesterday": lambda n: (n - timedelta(days=1)).strftime("%Y-%m-%d"),
    "tomorrow":  lambda n: (n + timedelta(days=1)).strftime("%Y-%m-%d"),
    "now":       lambda n: n.strftime("%Y-%m-%d_%H-%M-%S"),
    "timestamp": lambda n: str(int(n.timestamp())),
    "iso":       lambda n: n.isoformat(),
}


class ExecutorAgent(BaseAgent):
    name = "ExecutorAgent"
    capabilities = ("execute",)

    def __init__(self, browser=None, registry: AgentRegistry = None, **kw):
        super().__init__(**kw)
        self.browser = browser
        self.registry = registry
        self._thread = None

    def _extract_url(self, step: str) -> Optional[str]:
        m = _URL_RE.search(step)
        if not m:
            return None
        url = m.group(1)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _substitute_placeholders(self, text: str, results: list) -> str:
        """Replace {{prev}}, {{stepN}}, {{all}} with prior step outputs."""
        import re

        def repl(match):
            key = match.group(1).strip().lower()
            if key == "prev" and results:
                return str(results[-1][1])
            if key == "all":
                return "\n\n".join(f"Step: {s}\nResult: {r}" for s, r in results)
            m2 = re.match(r"step\s*(\d+)", key)
            if m2:
                idx = int(m2.group(1)) - 1
                if 0 <= idx < len(results):
                    return str(results[idx][1])
            # Date placeholders work even without prior results
            date_fn = _DATE_KEYS.get(key)
            if date_fn:
                return date_fn(datetime.now())
            return match.group(0)

        return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", repl, text)

    def _resolve_agent(self, name: str):
        """Resolve 'web', 'WebAgent', 'web_agent' → WebAgent instance."""
        if not self.registry:
            return None
        key = name.strip().lower()

        # 1. direct hit
        agent = self.registry.get(name.strip())
        if agent:
            return agent

        # 2. alias map
        mapped = AGENT_ALIASES.get(key)
        if mapped:
            agent = self.registry.get(mapped)
            if agent:
                return agent

        # 3. try capitalized + "Agent"
        guess = f"{key.capitalize()}Agent"
        agent = self.registry.get(guess)
        if agent:
            return agent

        # 4. case-insensitive search of registered names
        for reg_name, reg_agent in self.registry.all().items():
            if reg_name.lower() == key or reg_name.lower().startswith(key):
                return reg_agent
        return None

    def execute_step(self, step: str) -> str:
        s = step.lower()

        # explicit agent routing: "web: ...", "knowledge: ...", etc.
        if ":" in step:
            agent_name, payload = step.split(":", 1)
            if len(agent_name) <= 20 and " " not in agent_name.strip():
                agent = self._resolve_agent(agent_name)
                if agent:
                    try:
                        return str(agent.run(payload.strip()))
                    except Exception as e:
                        return f"[executor error in {agent_name.strip()}] {e}"

        # natural language: "open <url>"
        if self.browser and any(k in s for k in ("open", "fetch", "visit", "browse")):
            url = self._extract_url(step)
            if url:
                return self.browser.open_page(url)
            return f"[executor] no URL found in: {step}"

        # natural language: "search for ..."
        if self.browser and ("search" in s or "find" in s):
            return self.browser.search_and_extract(step)

        return f"Executed: {step}"

    def run(self, plan: list, goal: str = "") -> list:
        results = []
        for step in plan:
            resolved = self._substitute_placeholders(step, results)
            results.append((step, self.execute_step(resolved)))
        if self.bus:
            self.bus.send("critic", {"type": "results", "data": results, "goal": goal})
        return results

    def start(self) -> None:
        def loop():
            while not self.bus.stopped:
                msg = self.bus.receive("executor", timeout=0.5)
                if msg is None:
                    continue
                if msg.get("type") == SHUTDOWN:
                    break
                if msg.get("type") == "plan":
                    self.run(msg["data"], msg.get("goal", ""))
        self._thread = threading.Thread(target=loop, daemon=True, name="ExecutorAgent")
        self._thread.start()

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "execute":
            return str(self.execute_step(args[0]))
        return f"ExecutorAgent - command '{command}' not implemented."

    def shutdown(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)