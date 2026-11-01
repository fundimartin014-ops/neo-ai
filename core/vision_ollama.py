import requests
import base64

class VisionOllama:
    def __init__(self, model="moondream"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"
        
    def describe_image(self, image_path):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            
        payload = {
            "model": self.model,
            "prompt": "Describe this image in detail.",
            "images": [img_b64],
            "stream": False
        }
        
        try:
            r = requests.post(self.url, json=payload, timeout=60)
            r.raise_for_status()
            return r.json()["response"].strip()
        except Exception as e:
            return f"[Vision Error] {e}"
            
    def is_available(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            return self.model in [m["name"] for m in r.json().get("models", [])]
        except:
            return False