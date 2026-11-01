FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only the runtime dependencies we actually use
RUN pip install --upgrade pip && pip install \
    "pydantic>=2.6" \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "aiosqlite>=0.20" \
    "httpx>=0.27"

# Copy ONLY the agents package (skip the rest of the repo)
COPY agents/ ./agents/

# Runtime directories for persistence
RUN mkdir -p /app/data /app/sandbox

# Non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
 && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["python", "-m", "uvicorn", "agents.api_server:app", "--host", "0.0.0.0", "--port", "8000"]