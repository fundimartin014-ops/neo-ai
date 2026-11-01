# Multiagent Runtime

Async multi-agent runtime: bus + registry + persistent agents + FastAPI front door.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
cp .env.example .env
uvicorn agents.api_server:app --reload --port 8000
