import requests
import json

class DiscordWebhook:
    def __init__(self, url=None):
        self.url = url or "https://discord.com/api/webhooks/YOUR/WEBHOOK/URL"
        
    def send(self, message, username="Neo Bot"):
        if not self.url or "YOUR" in self.url:
            return False
        payload = {
            "content": message,
            "username": username
        }
        try:
            r = requests.post(
                self.url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            return r.status_code == 204
        except Exception as e:
            print(f"[Discord Error] {e}")
            return False