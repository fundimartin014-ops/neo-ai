#!/usr/bin/env python3
"""
slack_bot.py — Neo Hybrid Slack Bot
Run with: python slack_bot.py
"""

import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Neo imports (must be in same folder)
from hybrid_discord import HybridDiscordCommands
from neo_model_manager import get_model_manager

# ─── CONFIG ───
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")  # For Socket Mode

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in your .env")

# ─── SETUP APP ───
slack_app = App(token=SLACK_BOT_TOKEN)

# ─── REGISTER HYBRID COMMANDS ───
mm = get_model_manager()
hybrid_cmds = HybridDiscordCommands(model_manager=mm)
hybrid_cmds.register_slack_bolt(slack_app)

# ─── RUN ───
if __name__ == "__main__":
    print("💬 Slack bot starting in Socket Mode...")
    print("Try: /hybrid, /models, /stats, /strategies, /compare")
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()