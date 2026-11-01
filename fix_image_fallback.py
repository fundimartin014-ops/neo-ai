from pathlib import Path

content = '''"""ImageAnalysisAgent — analyze images via AWS Rekognition with local Ollama fallback.

Priority:
  1. AWS Rekognition (if AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY set)
  2. Ollama moondream (local, free, no keys) if AWS is missing or fails

Env vars (all optional):
  AWS_ACCESS_KEY_ID          -- enables Rekognition
  AWS_SECRET_ACCESS_KEY
  AWS_DEFAULT_REGION         -- default us-east-1
  OLLAMA_URL                 -- default http://localhost:11434
  NEO_VISION_MODEL           -- default moondream
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


class ImageAnalysisAgent(BaseAgent):
    name = "ImageAnalysisAgent"
    capabilities = ("image_analysis",)

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self._rek_client = None

    # ------------------------------------------------------------------ helpers
    def _have_aws(self) -> bool:
        return bool(
            os.getenv("AWS_ACCESS_KEY_ID")
            and os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def _resolve_file(self, path_str: str) -> str | None:
        """If path_str is a dir, pick the first image inside. Else return it as-is."""
        if not path_str:
            return None
        p = Path(path_str)
        if not p.exists():
            return None
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.suffix.lower() in IMAGE_EXTS:
                    return str(child)
            return None  # dir has no images
        return str(p)

    # ---------------------------------------------------------------- AWS engine
    def _aws_client(self):
        if self._rek_client is not None:
            return self._rek_client
        import boto3
        self._rek_client = boto3.client(
            "rekognition",
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        return self._rek_client

    def _aws_analyze(self, image_path: str, max_labels: int = 15,
                     min_confidence: float = 70.0) -> dict:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        client = self._aws_client()

        labels = []
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

        text = ""
        try:
            tr = client.detect_text(Image={"Bytes": image_bytes})
            parts = [d.get("DetectedText", "")
                     for d in tr.get("TextDetections", [])
                     if d.get("Type") == "LINE"]
            text = " ".join(parts).strip()
        except Exception:
            pass

        return {"backend": "aws-rekognition", "labels": labels, "text": text, "error": None}

    # -------------------------------------------------------------- Ollama engine
    def _ollama_analyze(self, image_path: str) -> dict:
        try:
            import httpx
        except ImportError:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": "httpx not installed"}
        try:
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        except Exception as e:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": f"read failed: {e}"}

        url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("NEO_VISION_MODEL", "moondream")

        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(
                    f"{url}/api/generate",
                    json={
                        "model": model,
                        "prompt": (
                            "List every distinct object, plant, animal, or scene "
                            "visible in this photo. Then, if there is any text, "
                            "copy it verbatim. Be concise."
                        ),
                        "images": [b64],
                        "stream": False,
                    },
                )
                r.raise_for_status()
                desc = r.json().get("response", "").strip()
        except Exception as e:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": f"ollama call failed: {e}"}

        # Convert free-text description into a single "description" entry
        return {
            "backend": f"ollama:{model}",
            "labels": [{"name": desc, "confidence": 100.0, "parents": []}] if desc else [],
            "text": "",
            "error": None,
        }

    # ---------------------------------------------------------------- public API
    def analyze(self, image_path: str, max_labels: int = 15,
                min_confidence: float = 70.0) -> dict:
        resolved = self._resolve_file(image_path)
        if resolved is None:
            msg = f"file not found or no images inside: {image_path}"
            if Path(image_path).is_dir():
                try:
                    names = [p.name for p in Path(image_path).iterdir()]
                    if names:
                        msg += f" (dir contains: {', '.join(names[:5])})"
                except Exception:
                    pass
            return {"backend": "none", "labels": [], "text": "", "error": msg}

        # Try AWS first if creds present
        if self._have_aws():
            try:
                res = self._aws_analyze(resolved, max_labels, min_confidence)
                if not res.get("error"):
                    return res
                self.logger.warning("[image_analysis] AWS failed: %s; falling back to Ollama",
                                    res.get("error"))
            except Exception as e:
                self.logger.warning("[image_analysis] AWS exception: %s; falling back to Ollama", e)

        # Fallback to Ollama (or primary if no AWS)
        return self._ollama_analyze(resolved)

    def format_for_llm(self, result: dict) -> str:
        if result.get("error"):
            return f"[image analysis error] {result['error']}"
        backend = result.get("backend", "?")
        lines = [f"[backend: {backend}]"]
        if result.get("labels"):
            lines.append("DETECTED OBJECTS / SCENES:")
            for l in result["labels"]:
                parent = f" ({', '.join(l['parents'])})" if l.get("parents") else ""
                lines.append(f"  - {l['name']} ({l['confidence']}%){parent}")
        if result.get("text"):
            lines.append("")
            lines.append(f"TEXT IN IMAGE: {result['text']}")
        return "\\n".join(lines) if len(lines) > 1 else "(no labels detected)"

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
print("Rewrote agents/image_analysis_agent.py with AWS + Ollama fallback")