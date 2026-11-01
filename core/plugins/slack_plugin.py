from core.discord_webhook import DiscordWebhook
import os

class Plugin:
    def __init__(self):
        self.webhook = DiscordWebhook(url=os.getenv("DISCORD_WEBHOOK_URL"))
        
    def run(self):
        print("[Chat] Discord webhook ready.")
        
    def send(self, msg):
        return self.webhook.send(msg)