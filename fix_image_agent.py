from pathlib import Path

content = '''"""ImageAnalysisAgent — detect labels and objects in images via AWS Rekognition."""
from __future__ import annotations

import os
from typing import Any

from agents.base_agent import BaseAgent


class ImageAnalysisAgent(BaseAgent):
    name = "ImageAnalysisAgent"
    capabilities = ("image_analysis",)

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self._client = None

    def _have_creds(self) -> bool:
        return bool(
            os.getenv("AWS_ACCESS_KEY_ID")
            and os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")
        self._client = boto3.client(
            "rekognition",
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        return self._client

    def analyze(self, image_path: str, max_labels: int = 15,
                min_confidence: float = 70.0) -> dict:
        if not self._have_creds():
            return {
                "labels": [],
                "text": "",
                "error": ("AWS credentials not configured. "
                          "Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
                          "and AWS_DEFAULT_REGION in .env"),
            }

        if not os.path.isfile(image_path):
            return {"labels": [], "text": "", "error": f"file not found: {image_path}"}

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            return {"labels": [], "text": "", "error": f"read failed: {e}"}

        try:
            client = self._get_client()
        except Exception as e:
            return {"labels": [], "text": "", "error": f"client init failed: {e}"}

        labels = []
        try:
            resp = client.detect_labels(
                Image={"Bytes": image_bytes},
                MaxLabels=int(max_labels),
                MinConfidence=float(min_confidence),
            )
            for label in resp.get("Labels", []):
                labels.append({
                    "name": label.get("Name", ""),
                    "confidence": round(label.get("Confidence", 0), 1),
                    "parents": [p.get("Name") for p in label.get("Parents", [])],
                })
        except Exception as e:
            return {"labels": [], "text": "", "error": f"detect_labels failed: {e}"}

        text = ""
        try:
            tr = client.detect_text(Image={"Bytes": image_bytes})
            parts = [d.get("DetectedText", "")
                     for d in tr.get("TextDetections", [])
                     if d.get("Type") == "LINE"]
            text = " ".join(parts).strip()
        except Exception:
            pass

        return {"labels": labels, "text": text, "error": None}

    def format_for_llm(self, result: dict) -> str:
        if result.get("error"):
            return f"[image analysis error] {result['error']}"
        lines = []
        if result.get("labels"):
            lines.append("DETECTED OBJECTS / SCENES:")
            for l in result["labels"]:
                parent = f" ({', '.join(l['parents'])})" if l["parents"] else ""
                lines.append(f"  - {l['name']} ({l['confidence']}%){parent}")
        if result.get("text"):
            lines.append("")
            lines.append(f"TEXT IN IMAGE: {result['text']}")
        return "\\n".join(lines) if lines else "(no labels detected)"

    def run(self, image_path: str = "", max_labels: int = 15) -> str:
        if not image_path:
            return "ImageAnalysisAgent: provide an image path."
        result = self.analyze(image_path, max_labels=max_labels)
        return self.format_for_llm(result)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "analyze":
            return self.run(args[0] if args else "")
        return f"ImageAnalysisAgent - command '{command}' not implemented."
'''

Path("agents/image_analysis_agent.py").write_text(content, encoding="utf-8")
print("Rewrote agents/image_analysis_agent.py (graceful + handle_command fixed)")