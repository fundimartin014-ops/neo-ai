# Multiagent sub-project

Self-contained agent runtime.

## Run from project root
    python -m agents "I love this"

## Run the HTTP API
    uvicorn agents.api_server:app --reload --port 8000

## Install as editable
    pip install -e "agents[dev]"
