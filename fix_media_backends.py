from pathlib import Path
import py_compile, re

root = Path(".").resolve()

# ============================================================
# 1. SURGICAL FIX to video_plugin.py
# ============================================================
vp = root / "core" / "plugins" / "video_plugin.py"
src = vp.read_text(encoding="utf-8")

# --- 1a. Replace the model list with currently-live Replicate official models
old_models = re.search(
    r"    REPLICATE_VIDEO_MODELS = \[.*?\]\n",
    src, re.DOTALL,
)
new_models = '''    # Live Replicate official models (no version hash needed).
    # Ordered highest-quality-first; falls through on failure.
    REPLICATE_VIDEO_MODELS = [
        "minimax/hailuo-02",
        "minimax/video-01",
        "kwaivgi/kling-v1.6-standard",
        "wan-video/wan-2.2-t2v-fast",
        "lightricks/ltx-video",
    ]
'''
if old_models:
    src = src.replace(old_models.group(0), new_models, 1)
    print("[ok] video: replaced REPLICATE_VIDEO_MODELS")
else:
    print("[warn] video: REPLICATE_VIDEO_MODELS not found")

# --- 1b. Fix _check_backends Replicate check: use /v1/account
old_check = re.search(
    r'(?:\s*)r\s*=\s*requests\.get\(\s*"https://api\.replicate\.com/v1/models/luma-ai/dream-machine",[^)]*\)',
    src, re.DOTALL,
)
if old_check:
    src = src.replace(
        old_check.group(0),
        '            r = requests.get("https://api.replicate.com/v1/account",\n'
        '                headers={"Authorization": f"Bearer {self.keys[\'replicate\']}"},\n'
        '                timeout=8)',
        1,
    )
    print("[ok] video: fixed Replicate backend check to /v1/account")
else:
    print("[warn] video: Replicate backend check pattern not found")

# --- 1c. Replace the whole _generate_replicate_video body with a version-hash-free version
new_method = '''    def _generate_replicate_video(self, prompt, seconds, width, height, seed):
        if not self.keys["replicate"]:
            return "[Video Error] Replicate: REPLICATE_API_TOKEN required."
        headers = {
            "Authorization": f"Bearer {self.keys['replicate']}",
            "Content-Type": "application/json",
        }
        import time
        last_error = ""
        for model in self.REPLICATE_VIDEO_MODELS:
            owner, _, name = model.partition("/")
            url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
            payload = {"input": {"prompt": prompt}}
            if width and height:
                payload["input"]["aspect_ratio"] = (
                    "16:9" if width >= height else "9:16"
                )
            if seconds:
                payload["input"]["duration"] = int(seconds)
            try:
                r = requests.post(url, headers=headers,
                                  data=json.dumps(payload), timeout=30)
                if r.status_code == 402:
                    return "[Video Error] Replicate: prepaid credit exhausted."
                if r.status_code >= 300:
                    last_error = f"{model} HTTP {r.status_code}: {r.text[:120]}"
                    continue
                data = r.json()
                if data.get("output"):
                    return self._download_video(data["output"], prompt,
                                                f"replicate-{name}")
                pid = data.get("id")
                if pid:
                    out = self._poll_replicate_video(pid, prompt,
                                                     f"replicate-{name}")
                    if out and not out.startswith("[Video Error]"):
                        return out
                    last_error = out or last_error
            except Exception as e:
                last_error = f"{model} {type(e).__name__}: {e}"
                continue
        return f"[Video Error] Replicate: all models failed. Last: {last_error}"
'''
# Find current _generate_replicate_video — from 'def _generate_replicate_video' to
# the next 'def ' at same indent
m = re.search(
    r"    def _generate_replicate_video\(self, prompt, seconds, width, height, seed\):.*?(?=\n    def )",
    src, re.DOTALL,
)
if m:
    src = src[:m.start()] + new_method + src[m.end():]
    print("[ok] video: rewrote _generate_replicate_video to version-hash-free")
else:
    print("[warn] video: _generate_replicate_video not found")

# --- 1d. Fix error message (Replicate token WAS present)
old_msg = (
    '            f"→ Add REPLICATE_API_TOKEN to .env for best quality (Luma Dream Machine)\\n"\n'
    '            f"→ Or add HF_TOKEN for free Zeroscope generation"'
)
new_msg = (
    '            f"→ Check .env keys and network access.\\n"\n'
    '            f"→ Replicate status: {self._backends.get(\'replicate\')}\\n"\n'
    '            f"→ HuggingFace status: {self._backends.get(\'huggingface\')}"'
)
if old_msg in src:
    src = src.replace(old_msg, new_msg, 1)
    print("[ok] video: fixed misleading error message")
else:
    print("[warn] video: error message anchor not found")

vp.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(vp), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] video_plugin.py: {e}")
    raise SystemExit(1)

# ============================================================
# 2. REWRITE vision_plugin.py as multi-backend
# ============================================================
vis_src = '''"""Vision plugin - text-to-image generation via multi-backend router.

Priority (highest quality first):
  Replicate (Flux 1.1 Pro / Flux Dev / SD 3.5)  ->  needs REPLICATE_API_TOKEN
  Fal.ai    (Flux Schnell / Dev / Pro)           ->  needs FAL_KEY
  Ideogram  (best for text-in-image)             ->  needs IDEOGRAM_API_KEY
  Clipdrop  (free tier, decent)                  ->  needs CLIPDROP_API_KEY
  DeepAI    (basic, works)                       ->  needs DEEPAI_API_KEY
  Pollinations (always free, no key)             ->  always available

Also supports image DESCRIBE via Ollama moondream (existing path).

CLI: generate <prompt> [width] [height] [backend=<name>]
"""
from __future__ import annotations
import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False


GENERATED_DIR = Path("generated_images")
GENERATED_DIR.mkdir(exist_ok=True)


# Backends in priority order (id, name, key_env)
BACKENDS = [
    # id,             needs env,                highest quality → fastest
    ("replicate",     "REPLICATE_API_TOKEN"),
    ("fal",           "FAL_KEY"),
    ("ideogram",      "IDEOGRAM_API_KEY"),
    ("clipdrop",      "CLIPDROP_API_KEY"),
    ("deepai",        "DEEPAI_API_KEY"),
    ("pollinations",  None),                    # always available
]


class Plugin:
    name = "vision"

    POLLINATIONS_URL = (
        "https://image.pollinations.ai/prompt/{prompt}"
        "?width={width}&height={height}&nologo=true&seed={seed}&model=flux"
    )

    REPLICATE_MODELS = [
        # Fast/cheap first, quality second — for cost safety.
        "black-forest-labs/flux-schnell",
        "black-forest-labs/flux-dev",
        "black-forest-labs/flux-1.1-pro",
    ]
    FAL_MODELS = [
        "fal-ai/flux/schnell",
        "fal-ai/flux/dev",
        "fal-ai/flux-pro/v1.1",
    ]

    def __init__(self):
        self.keys = {
            "replicate":  os.getenv("REPLICATE_API_TOKEN", "").strip(),
            "fal":        (os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY") or "").strip(),
            "ideogram":   os.getenv("IDEOGRAM_API_KEY", "").strip(),
            "clipdrop":   os.getenv("CLIPDROP_API_KEY", "").strip(),
            "deepai":     os.getenv("DEEPAI_API_KEY", "").strip(),
            "pollinations": "always",
        }
        self._backends: Dict[str, bool] = {}
        self.temp_dir = GENERATED_DIR
        self._check_backends()

    def _check_backends(self):
        for bid, key_env in BACKENDS:
            if key_env is None:
                self._backends[bid] = True
                continue
            self._backends[bid] = bool(self.keys.get(bid))
        active = [k for k, v in self._backends.items() if v]
        logger.info("[Vision] Active backends (%d): %s", len(active), ", ".join(active))

    def run(self):
        return "Vision plugin ready."

    # ---------- public API ----------
    def generate(self, prompt, width=1024, height=768, model_hint=None, seed=None):
        if not _HAS_REQ:
            return "[Vision Error] requests library not installed."
        if not prompt or not prompt.strip():
            return "[Vision Error] empty prompt."

        prompt = prompt.strip()
        seed = seed or int(time.time()) % 1_000_000

        order = self._backend_order(model_hint)
        errors = []

        for bid in order:
            try:
                if bid == "replicate":
                    out = self._gen_replicate(prompt, width, height, seed)
                elif bid == "fal":
                    out = self._gen_fal(prompt, width, height, seed)
                elif bid == "ideogram":
                    out = self._gen_ideogram(prompt, width, height, seed)
                elif bid == "clipdrop":
                    out = self._gen_clipdrop(prompt, width, height)
                elif bid == "deepai":
                    out = self._gen_deepai(prompt, width, height)
                elif bid == "pollinations":
                    out = self._gen_pollinations(prompt, width, height, seed)
                else:
                    continue

                if out and not out.startswith("[Vision Error]"):
                    return out
                if out:
                    errors.append(f"{bid}: {out[:80]}")
            except Exception as e:
                errors.append(f"{bid}: {type(e).__name__}: {e}")

        msg = "\\n  ".join(errors) if errors else "(no backends ran)"
        return f"[Vision Error] all backends failed.\\n  {msg}"

    def _backend_order(self, hint):
        if hint:
            hint = hint.lower()
            aliases = {
                "replicate": "replicate", "rep": "replicate",
                "fal": "fal", "falai": "fal",
                "ideogram": "ideogram", "ideo": "ideogram",
                "clipdrop": "clipdrop", "cd": "clipdrop",
                "deepai": "deepai", "da": "deepai",
                "pollinations": "pollinations", "poll": "pollinations",
                "flux": "replicate",  # flux lives on replicate/fal; use replicate default
            }
            if hint in aliases:
                target = aliases[hint]
                # move target to front, keep fallbacks
                rest = [b for b in self._backends if b != target]
                return [target] + rest
        # default priority order, filtered by availability
        priority = ["replicate", "fal", "ideogram", "clipdrop", "deepai", "pollinations"]
        return [b for b in priority if self._backends.get(b)]

    # ---------- helpers ----------
    def _save(self, content: bytes, prompt: str, backend: str, ext="jpg") -> str:
        safe = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_") or "image"
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = GENERATED_DIR / f"neo_{backend}_{safe}_{ts}.{ext}"
        path.write_bytes(content)
        logger.info("[Vision] Image saved: %s", path)
        return f"[Vision] Image generated: {path}"

    def _download(self, url: str, prompt: str, backend: str) -> str:
        r = requests.get(url, timeout=120)
        if r.status_code >= 300:
            return f"[Vision Error] download HTTP {r.status_code}"
        return self._save(r.content, prompt, backend)

    # ---------- Replicate ----------
    def _gen_replicate(self, prompt, w, h, seed):
        tok = self.keys["replicate"]
        if not tok:
            return "[Vision Error] Replicate: no token."
        headers = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        }
        last = ""
        for model in self.REPLICATE_MODELS:
            owner, _, name = model.partition("/")
            url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
            payload = {
                "input": {
                    "prompt": prompt,
                    "width": w,
                    "height": h,
                    "num_outputs": 1,
                }
            }
            r = requests.post(url, headers=headers,
                              data=json.dumps(payload), timeout=30)
            if r.status_code == 402:
                return "[Vision Error] Replicate: prepaid credit exhausted."
            if r.status_code >= 300:
                last = f"{model}: HTTP {r.status_code}"
                continue
            data = r.json()
            out = data.get("output")
            if out:
                url_out = out[0] if isinstance(out, list) else out
                return self._download(url_out, prompt, f"replicate_{name}")
            pid = data.get("id")
            if pid:
                # poll up to 90s
                for _ in range(45):
                    time.sleep(2)
                    pr = requests.get(
                        f"https://api.replicate.com/v1/predictions/{pid}",
                        headers={"Authorization": f"Bearer {tok}"}, timeout=15,
                    )
                    if pr.status_code >= 300:
                        continue
                    pd = pr.json()
                    status = pd.get("status")
                    if status == "succeeded" and pd.get("output"):
                        url_out = pd["output"][0] if isinstance(pd["output"], list) else pd["output"]
                        return self._download(url_out, prompt, f"replicate_{name}")
                    if status in ("failed", "canceled"):
                        last = f"{model}: {pd.get('error', status)}"
                        break
        return f"[Vision Error] Replicate: all models failed. Last: {last}"

    # ---------- Fal.ai ----------
    def _gen_fal(self, prompt, w, h, seed):
        key = self.keys["fal"]
        if not key:
            return "[Vision Error] Fal: no key."
        headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
        last = ""
        for model in self.FAL_MODELS:
            url = f"https://fal.run/{model}"
            payload = {
                "prompt": prompt,
                "image_size": {"width": w, "height": h},
                "num_images": 1,
            }
            r = requests.post(url, headers=headers,
                              data=json.dumps(payload), timeout=60)
            if r.status_code >= 300:
                last = f"{model}: HTTP {r.status_code}"
                continue
            data = r.json()
            imgs = data.get("images") or []
            if imgs:
                return self._download(imgs[0]["url"], prompt, "fal")
        return f"[Vision Error] Fal: all models failed. Last: {last}"

    # ---------- Ideogram ----------
    def _gen_ideogram(self, prompt, w, h, seed):
        key = self.keys["ideogram"]
        if not key:
            return "[Vision Error] Ideogram: no key."
        # Ideogram uses multipart form
        form = {
            "prompt": (None, prompt),
            "aspect_ratio": (None, "16x9" if w >= h else "9x16"),
            "model": (None, "V_2"),
        }
        r = requests.post("https://api.ideogram.ai/generate",
                          headers={"Api-Key": key}, files=form, timeout=60)
        if r.status_code >= 300:
            return f"[Vision Error] Ideogram HTTP {r.status_code}: {r.text[:100]}"
        data = r.json()
        items = data.get("data") or []
        if items:
            return self._download(items[0]["url"], prompt, "ideogram")
        return "[Vision Error] Ideogram: no image returned."

    # ---------- Clipdrop ----------
    def _gen_clipdrop(self, prompt, w, h):
        key = self.keys["clipdrop"]
        if not key:
            return "[Vision Error] Clipdrop: no key."
        r = requests.post(
            "https://clipdrop-api.co/text-to-image/v1",
            headers={"x-api-key": key},
            files={"prompt": (None, prompt)},
            timeout=60,
        )
        if r.status_code >= 300:
            return f"[Vision Error] Clipdrop HTTP {r.status_code}"
        if "image" not in r.headers.get("content-type", ""):
            return f"[Vision Error] Clipdrop: {r.content[:100]}"
        return self._save(r.content, prompt, "clipdrop")

    # ---------- DeepAI ----------
    def _gen_deepai(self, prompt, w, h):
        key = self.keys["deepai"]
        if not key:
            return "[Vision Error] DeepAI: no key."
        r = requests.post(
            "https://api.deepai.org/api/text2img",
            data={"text": prompt},
            headers={"api-key": key},
            timeout=60,
        )
        if r.status_code >= 300:
            return f"[Vision Error] DeepAI HTTP {r.status_code}"
        j = r.json()
        url = j.get("output_url")
        if not url:
            return "[Vision Error] DeepAI: no output_url."
        return self._download(url, prompt, "deepai")

    # ---------- Pollinations (always available) ----------
    def _gen_pollinations(self, prompt, w, h, seed):
        url = self.POLLINATIONS_URL.format(
            prompt=requests.utils.quote(prompt),
            width=w, height=h, seed=seed,
        )
        logger.info("[Vision] Pollinations request: %s", url)
        r = requests.get(url, timeout=120)
        if r.status_code >= 300:
            return f"[Vision Error] Pollinations HTTP {r.status_code}"
        ct = r.headers.get("content-type", "")
        if not ct.startswith("image"):
            return f"[Vision Error] Pollinations returned {ct}"
        return self._save(r.content, prompt, "pollinations")

    # ---------- describe (existing Ollama path) ----------
    def describe(self, image_path, prompt="Describe this image."):
        try:
            with open(image_path, "rb") as f:
                img = f.read()
        except Exception as e:
            return f"[Vision Error] cannot read {image_path}: {e}"
        b64 = base64.b64encode(img).decode("ascii")
        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "moondream", "prompt": prompt,
                      "images": [b64], "stream": False},
                timeout=120,
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        except Exception as e:
            return f"[Vision Error] ollama: {e}"
        return "[Vision Error] no vision backend available."
'''
(root / "core" / "plugins" / "vision_plugin.py").write_text(vis_src, encoding="utf-8")
print("[ok] rewrote vision_plugin.py")
try:
    py_compile.compile(str(root / "core" / "plugins" / "vision_plugin.py"), doraise=True)
    print("[ok] vision_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] vision_plugin.py: {e}")
    raise SystemExit(1)

print()
print("=" * 72)
print("  Phase 1 done: video + vision backends fixed.")
print("=" * 72)
print("Restart the launcher and test:")
print('  > generate image of a dancing baby')
print('  > generate video of a dancing baby')
print()
print("Then Phase 2: phone control modules get written next.")