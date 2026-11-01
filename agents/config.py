import os
from pathlib import Path

def _bool(v: str | None, default: bool = False) -> bool:
    return default if v is None else v.lower() in {"1", "true", "yes", "on"}

class Config:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_JSON: bool = _bool(os.getenv("LOG_JSON"), True)

    DB_PATH: str = os.getenv("DB_PATH", "./data/agents.db")
    FILE_AGENT_ROOT: str = os.getenv("FILE_AGENT_ROOT", "./sandbox")

    API_AGENT_TOKEN: str = os.getenv("API_AGENT_TOKEN", "")
    API_AGENT_BASE_URL: str = os.getenv("API_AGENT_BASE_URL", "")
    API_AGENT_TIMEOUT: float = float(os.getenv("API_AGENT_TIMEOUT", "10"))

    WEB_TIMEOUT: float = float(os.getenv("WEB_TIMEOUT", "10"))
    WEB_USER_AGENT: str = os.getenv("WEB_USER_AGENT", "multiagent/1.0")
    SESSION_TIMEOUT: float = float(os.getenv("SESSION_TIMEOUT", "3600"))

    @classmethod
    def ensure_dirs(cls) -> None:
        Path(cls.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(cls.FILE_AGENT_ROOT).mkdir(parents=True, exist_ok=True)