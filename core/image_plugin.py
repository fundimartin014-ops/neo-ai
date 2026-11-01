class ImagePlugin:
    def __init__(self, replicate_key):
        self.key = replicate_key
    
    def generate(self, prompt, width=1024, height=768):
        url = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
        headers = {
            "Authorization": f"Token {self.key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": {
                "prompt": prompt,
                "aspect_ratio": f"{width}:{height}"
            }
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        # ...poll for image URL...
        return image_url