#!/usr/bin/env python3
"""
discord_bot.py — Neo Hybrid Discord Bot
Run with: python discord_bot.py
"""

import os
import asyncio
import discord
from discord import app_commands

# Neo imports (must be in same folder)
from hybrid_discord import HybridDiscordCommands
from neo_model_manager import get_model_manager

# ─── CONFIG ───
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Set DISCORD_BOT_TOKEN in your .env file")

# ─── SETUP CLIENT ───
intents = discord.Intents.default()
intents.message_content = True  # Needed if you add text commands later

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ─── REGISTER HYBRID COMMANDS ───
mm = get_model_manager()
hybrid_cmds = HybridDiscordCommands(bot=client, model_manager=mm)
hybrid_cmds.register_discord_py(tree)

# ─── EVENTS ───
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Discord bot logged in as {client.user}")
    print("🤖 Hybrid slash commands synced!")
    print("Try: /hybrid, /models, /stats, /strategies, /compare")

# ─── RUN ───
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)