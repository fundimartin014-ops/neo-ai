import requests

class Notifier:
    def __init__(self, topic="fundi-neo-bot"):
        self.topic = topic
        self.url = f"https://ntfy.sh/{topic}"
        
    def send(self, message, title="Neo Alert", priority="default"):
        """
        priority: 'min', 'low', 'default', 'high', 'urgent'
        """
        try:
            r = requests.post(
                self.url,
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": "robot,warning"
                },
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            print(f"[Notify Error] {e}")
            return False