from pathlib import Path

content = '''"""ImageAnalysisAgent — analyze images via AWS Rekognition with local Ollama fallback."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
MIN_BYTES = 200


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

    def _clean_path(self, s: str) -> str:
        s = (s or "").strip()
        # Strip surrounding single or double quotes (in case preflight passed them through)
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("\\"", "'"):
            s = s[1:-1]
        return s.strip()

    def _is_real_image(self, p: Path) -> bool:
        try:
            return p.is_file() and p.stat().st_size >= MIN_BYTES
        except Exception:
            return False

    def _resolve_file(self, path_str: str) -> tuple[str | None, str]:
        """Return (resolved_path_or_None, diagnostic_message)."""
        path_str = self._clean_path(path_str)
        if not path_str:
            return None, "empty path"

        p = Path(path_str)
        if not p.exists():
            return None, f"path does not exist: {path_str}"

        if p.is_file():
            if not self._is_real_image(p):
                size = -1
                try:
                    size = p.stat().st_size
                except Exception:
                    pass
                return None, f"file is empty or too small ({size} bytes): {p.name}"
            return str(p), ""

        # Directory: find first real image
        candidates = []
        try:
            for child in sorted(p.iterdir()):
                if child.suffix.lower() in IMAGE_EXTS:
                    candidates.append(child)
        except Exception as e:
            return None, f"cannot read directory: {e}"

        if not candidates:
            names = []
            try:
                names = [x.name for x in sorted(p.iterdir())][:8]
            except Exception:
                pass
            hint = f" (dir contains: {', '.join(names)})" if names else ""
            return None, f"no image files in directory: {path_str}{hint}"

        for c in candidates:
            if self._is_real_image(c):
                return str(c), ""
            # skip empty files silently
        sizes = [(c.name, c.stat().st_size) for c in candidates]
        return None, f"all {len(candidates)} images are empty/too small: {sizes[:5]}"

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
            data = Path(image_path).read_bytes()
        except Exception as e:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": f"read failed: {e}"}
        if len(data) < MIN_BYTES:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": f"image too small ({len(data)} bytes)"}

        b64 = base64.b64encode(data).decode("ascii")
        url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("NEO_VISION_MODEL", "moondream")

        try:
            with httpx.Client(timeout=90) as c:
                r = c.post(
                    f"{url}/api/generate",
                    json={
                        "model": model,
                        "prompt": (
                            "Describe what is in this photo in one sentence. "
                            "Then, if there is any visible text, copy it verbatim."
                        ),
                        "images": [b64],
                        "stream": False,
                    },
                )
                if r.status_code != 200:
                    detail = r.text[:200]
                    return {"backend": "ollama", "labels": [], "text": "",
                            "error": f"ollama HTTP {r.status_code}: {detail}"}
                desc = r.json().get("response", "").strip()
        except Exception as e:
            return {"backend": "ollama", "labels": [], "text": "",
                    "error": f"ollama call failed: {e}"}

        return {
            "backend": f"ollama:{model}",
            "labels": [{"name": desc, "confidence": 100.0, "parents": []}] if desc else [],
            "text": "",
            "error": None,
        }

    # ---------------------------------------------------------------- public API
    def analyze(self, image_path: str, max_labels: int = 15,
                min_confidence: float = 70.0) -> dict:
        resolved, reason = self._resolve_file(image_path)
        if resolved is None:
            return {"backend": "none", "labels": [], "text": "",
                    "error": f"{reason}"}

        if self._have_aws():
            try:
                res = self._aws_analyze(resolved, max_labels, min_confidence)
                if not res.get("error"):
                    return res
                self.logger.info(
                    "[image_analysis] AWS denied (%s); using Ollama fallback",
                    str(res.get("error"))[:120],
                )
            except Exception as e:
                self.logger.info(
                    "[image_analysis] AWS error (%s); using Ollama fallback",
                    str(e)[:120],
                )

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
        return "\\n".join(lines) if len(lines) > 1 else "[no labels detected]"

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
print("Rewrote agents/image_analysis_agent.py (polish: skip tiny files, strip quotes, clearer errors)")