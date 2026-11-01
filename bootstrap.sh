#!/usr/bin/env bash
# bootstrap.sh — create the full multiagent project tree (Tier 1 + 2 + 3)
# usage:  bash bootstrap.sh [target-dir]
set -euo pipefail

ROOT="${1:-.}"
mkdir -p "$ROOT"
cd "$ROOT"
mkdir -p agents/llm agents/persistence tests data sandbox

# ============================================================================
# 1. ROOT FILES
# ============================================================================

cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "multiagent"
version = "0.3.0"
description = "Multi-agent orchestration runtime"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "aiosqlite>=0.20",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.1","pytest-asyncio>=0.23","pytest-cov>=5.0","ruff>=0.4","mypy>=1.9"]
redis = ["redis>=5.0"]
otel = [
    "opentelemetry-api>=1.24",
    "opentelemetry-sdk>=1.24",
    "opentelemetry-exporter-otlp>=1.24",
    "opentelemetry-instrumentation-fastapi>=0.45b0",
    "opentelemetry-instrumentation-httpx>=0.45b0",
    "opentelemetry-instrumentation-logging>=0.45b0",
]
all = ["multiagent[redis,otel]"]

[tool.setuptools.packages.find]
include = ["agents*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py311"
EOF

cat > Dockerfile << 'EOF'
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md* ./
RUN pip install --upgrade pip && pip install ".[redis,otel]"
COPY agents ./agents
COPY tests ./tests
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /app/data /app/sandbox && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
CMD ["uvicorn","agents.api_server:app","--host","0.0.0.0","--port","8000"]
EOF

cat > docker-compose.yml << 'EOF'
services:
  api:
    build: .
    image: multiagent:0.3.0
    ports: ["8000:8000"]
    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      LOG_JSON: "true"
      DB_PATH: /app/data/agents.db
      BUS_BACKEND: ${BUS_BACKEND:-memory}
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
      API_AGENT_TOKEN: ${API_AGENT_TOKEN:-}
      API_AGENT_BASE_URL: ${API_AGENT_BASE_URL:-}
      LLM_API_KEY: ${LLM_API_KEY:-}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o-mini}
      OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-}
    volumes:
      - ./data:/app/data
      - ./sandbox:/app/sandbox
    depends_on: [redis]
    restart: unless-stopped
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes: [redisdata:/data]
volumes:
  redisdata:
EOF

cat > .env.example << 'EOF'
LOG_LEVEL=INFO
LOG_JSON=true
DB_PATH=./data/agents.db
FILE_AGENT_ROOT=./sandbox
API_AGENT_TOKEN=
API_AGENT_BASE_URL=
API_AGENT_TIMEOUT=10
WEB_TIMEOUT=10
SESSION_TIMEOUT=3600
BUS_BACKEND=memory
REDIS_URL=redis://localhost:6379/0
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
OTEL_EXPORTER_OTLP_ENDPOINT=
ENV=dev
EOF

cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.venv/
venv/
.env
data/
sandbox/
*.db
*.db-wal
*.db-shm
.pytest_cache/
.ruff_cache/
.mypy_cache/
dist/
build/
*.egg-info/
EOF

cat > README.md << 'EOF'
# Multiagent Runtime

Async multi-agent runtime: bus + registry + persistent agents + FastAPI front door.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
cp .env.example .env
uvicorn agents.api_server:app --reload --port 8000