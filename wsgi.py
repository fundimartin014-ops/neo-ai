#!/usr/bin/env python3
"""
wsgi.py — Production WSGI Entry Point for TRAININGBOT2
=======================================================
This file initializes Neo AI and exposes the Flask app for Gunicorn.

Usage:
    gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# ─── PROJECT ROOT ───
PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── LOAD ENV ───
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(str(env_path), override=True)
        logger.info("[WSGI] Loaded .env")
except ImportError:
    pass

# ─── INITIALIZE NEO ───
logger.info("[WSGI] Initializing Neo AI...")

try:
    # Import from launcher.py (production entry point)
    from launcher import (
        load_plugins, init_llm, init_agent_core, init_brain,
        API_HOST, API_PORT
    )

    # Ensure directories
    for d in ["data/vector_store", "data", "logs", "temp/spreadsheets"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Load plugins
    plugins = load_plugins()
    logger.info(f"[WSGI] Plugins loaded: {len(plugins)}")

    # Run startup hooks
    for plugin in plugins:
        try:
            if hasattr(plugin, "run"): 
                plugin.run()
        except Exception as e:
            logger.error(f"[WSGI] Plugin startup error: {e}")

    # Init LLM
    llm = init_llm()

    # Init Agent Core
    agent_core = init_agent_core(plugins)

    # Init Brain
    brain = init_brain(plugins, llm, agent_core)

    if not hasattr(brain, "respond") or not callable(getattr(brain, "respond")):
        raise RuntimeError("FundiBrain has no 'respond' method")

    logger.info("[WSGI] FundiBrain is ready.")

    # ─── CREATE FLASK APP ───
    from launcher import NeoAPIServer
    server = NeoAPIServer(brain, agent_core, llm)

    # Expose the Flask app for Gunicorn
    app = server.app

    if app is None:
        raise RuntimeError("Flask app failed to initialize")

    logger.info(f"[WSGI] Flask app ready at http://{API_HOST}:{API_PORT}")

except Exception as e:
    logger.critical(f"[WSGI] Fatal initialization error: {e}")
    traceback.print_exc()
    # Create a fallback error app
    from flask import Flask
    app = Flask(__name__)

    @app.route("/")
    def error_index():
        return "<h1>Neo AI Error</h1><p>Failed to initialize. Check logs.</p>", 503

    @app.route("/api/health")
    def error_health():
        return {"status": "error", "message": str(e)}, 503
