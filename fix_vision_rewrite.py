from pathlib import Path
import py_compile

root = Path(".").resolve()

# ============================================================
# 1. REWRITE vision_plugin.py — actually run this time
# ============================================================
vis_src = '''"""Vision plugin — text-to-image + describe, multi-backend.

Priority order (first available wins, falls through on any failure):
  Replicate  → Flux Schnell/Dev/1.1 Pro     (needs REPLICATE_API_TOKEN)
  Fal.ai     → Flux Schnell/Dev/Pro         (needs FAL_KEY)
  Ideogram   → V_2 (best for text-in-image) (needs IDEOGRAM_API_KEY)
  Clipdrop   → text-to-image v1             (needs CLIPDROP_API_KEY)
  DeepAI     → text2img                     (needs DEEPAI_API_KEY)
  Pollinations → Flux, always available     (uses POLLINATIONS_API_KEY if present)

CLI:
  generate <prompt> [width] [height] [backend=<name>]
  describe <image_path>
"""
from __future__ import annotations
import base64
import json
import logging
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False


GENERATED_DIR = Path("generated_images")
GENERATED_DIR.mkdir(exist_ok=True)

# (backend_id, key_env_var) in priority order; pollinations has no key requirement
BACKENDS = [
    ("replicate",    "REPLICATE_API_TOKEN"),
    ("fal",          "FAL_KEY"),
    ("ideogram",     "IDEOGRAM_API_KEY"),
    ("clipdrop",     "CLIPDROP_API_KEY"),
    ("deepai",       "DEEPAI_API_KEY"),
    ("pollinations", None),
]


class Plugin:
    name = "vision"

    REPLICATE_MODELS = [
        "black-forest-labs/flux-schnell",   # cheapest on Replicate
        "black-forest-labs/flux-dev",
        "black-forest-labs/flux-1.1-pro",
    ]
    FAL_MODELS = [
        "fal-ai/flux/schnell",
        "fal-ai/flux/dev",
        "fal-ai/flux-pro/v1.1",
    ]
    POLLINATIONS_URL = (
        "https://image.pollinations.ai/prompt/{prompt}"
        "?width={width}&height={height}&nologo=true&seed={seed}&model=flux"
    )

    def __init__(self):
        self.keys = {
            "replicate":    os.getenv("REPLICATE_API_TOKEN", "").strip(),
            "fal":          (os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY") or "").strip(),
            "ideogram":     os.getenv("IDEOGRAM_API_KEY", "").strip(),
            "clipdrop":     os.getenv("CLIPDROP_API_KEY", "").strip(),
            "deepai":       os.getenv("DEEPAI_API_KEY", "").strip(),
            "pollinations": (os.getenv("POLLINATIONS_API_KEY") or "").strip(),
        }
        self.temp_dir = GENERATED_DIR
        self._backends: Dict[str, bool] = {}
        self._check_backends()

    def _check_backends(self):
        for bid, key_env in BACKENDS:
            if key_env is None:
                # pollinations: always available (key improves rate limits)
                self._backends[bid] = True
                continue
            self._backends[bid] = bool(self.keys.get(bid))
        active = [k for k, v in self._backends.items() if v]
        keyed = [k for k in active if k != "pollinations"]
        logger.info("[Vision] Active backends (%d): %s",
                    len(active), ", ".join(active))
        print(f"[Vision] Backends ready ({len(active)}): {', '.join(active)}")
        if keyed:
            print(f"[Vision] Keyed backends: {', '.join(keyed)}")

    def run(self):
        return "Vision plugin ready."

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def generate(self, prompt, width=1024, height=768, model_hint=None, seed=None):
        if not _HAS_REQ:
            return "[Vision Error] requests not installed."
        if not prompt or not prompt.strip():
            return "[Vision Error] empty prompt."
        prompt = prompt.strip()
        seed = seed or (int(time.time()) % 1_000_000)

        order = self._backend_order(model_hint)
        errors: List[str] = []

        for bid in order:
            try:
                if bid == "replicate":
                    out = self._gen_replicate(prompt, width, height, seed)
                elif bid == "fal":
                    out = self._gen_fal(prompt, width, height, seed)
                elif bid == "ideogram":
                    out = self._gen_ideogram(prompt, width, height)
                elif bid == "clipdrop":
                    out = self._gen_clipdrop(prompt, width, height)
                elif bid == "deepai":
                    out = self._gen_deepai(prompt, width, height)
                elif bid == "pollinations":
                    out = self._gen_pollinations(prompt, width, height, seed)
                else:
                    continue
            except Exception as e:
                errors.append(f"{bid}: {type(e).__name__}: {e}")
                continue

            if out and not out.startswith("[Vision Error]"):
                return out
            if out:
                errors.append(out[:120])

        if not errors:
            return "[Vision Error] no backends available."
        lines = "\\n  ".join(errors)
        return f"[Vision Error] all backends failed:\\n  {lines}"

    def _backend_order(self, hint):
        priority = ["replicate", "fal", "ideogram", "clipdrop",
                    "deepai", "pollinations"]
        if hint:
            h = hint.lower()
            aliases = {
                "replicate": "replicate", "rep": "replicate",
                "fal": "fal", "falai": "fal", "fal.ai": "fal",
                "ideogram": "ideogram", "ideo": "ideogram",
                "clipdrop": "clipdrop", "cd": "clipdrop",
                "deepai": "deepai", "da": "deepai",
                "pollinations": "pollinations", "poll": "pollinations",
                "flux": "replicate",
            }
            target = aliases.get(h)
            if target:
                rest = [b for b in priority if b != target
                        and self._backends.get(b)]
                return ([target] if self._backends.get(target) else []) + rest
        return [b for b in priority if self._backends.get(b)]

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _save(self, content: bytes, prompt: str, backend: str,
              ext: str = "jpg") -> str:
        safe = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_") or "image"
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = GENERATED_DIR / f"neo_{backend}_{safe}_{ts}.{ext}"
        path.write_bytes(content)
        logger.info("[Vision] saved %s", path)
        return f"[Vision] Image generated: {path}"

    def _download(self, url, prompt, backend, ext="jpg"):
        r = requests.get(url, timeout=120)
        if r.status_code >= 300:
            return f"[Vision Error] download HTTP {r.status_code}"
        return self._save(r.content, prompt, backend, ext)

    # ----------------------------------------------------------
    # Replicate
    # ----------------------------------------------------------
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
            url = (f"https://api.replicate.com/v1/models/"
                   f"{owner}/{name}/predictions")
            payload = {"input": {"prompt": prompt,
                                 "width": w, "height": h,
                                 "num_outputs": 1}}
            try:
                r = requests.post(url, headers=headers,
                                  data=json.dumps(payload), timeout=30)
            except Exception as e:
                last = f"{model}: {type(e).__name__}"
                continue
            if r.status_code == 402:
                return ("[Vision Error] Replicate: account needs credit. "
                        "Add payment at replicate.com/account/billing")
            if r.status_code == 401:
                return "[Vision Error] Replicate: invalid token."
            if r.status_code >= 300:
                last = f"{model}: HTTP {r.status_code}"
                continue
            data = r.json()
            out = data.get("output")
            if out:
                u = out[0] if isinstance(out, list) else out
                return self._download(u, prompt, f"replicate_{name}")
            pid = data.get("id")
            if pid:
                for _ in range(45):
                    time.sleep(2)
                    try:
                        pr = requests.get(
                            f"https://api.replicate.com/v1/predictions/{pid}",
                            headers={"Authorization": f"Bearer {tok}"},
                            timeout=15,
                        )
                    except Exception:
                        continue
                    if pr.status_code >= 300:
                        continue
                    pd = pr.json()
                    status = pd.get("status")
                    if status == "succeeded" and pd.get("output"):
                        out2 = pd["output"]
                        u = out2[0] if isinstance(out2, list) else out2
                        return self._download(u, prompt, f"replicate_{name}")
                    if status in ("failed", "canceled"):
                        last = f"{model}: {pd.get('error', status)}"
                        break
        return f"[Vision Error] Replicate: {last or 'no model succeeded'}"

    # ----------------------------------------------------------
    # Fal.ai
    # ----------------------------------------------------------
    def _gen_fal(self, prompt, w, h, seed):
        key = self.keys["fal"]
        if not key:
            return "[Vision Error] Fal: no key."
        headers = {"Authorization": f"Key {key}",
                   "Content-Type": "application/json"}
        last = ""
        for model in self.FAL_MODELS:
            url = f"https://fal.run/{model}"
            payload = {"prompt": prompt,
                       "image_size": {"width": w, "height": h},
                       "num_images": 1}
            try:
                r = requests.post(url, headers=headers,
                                  data=json.dumps(payload), timeout=90)
            except Exception as e:
                last = f"{model}: {type(e).__name__}"
                continue
            if r.status_code >= 300:
                last = f"{model}: HTTP {r.status_code} {r.text[:80]}"
                continue
            data = r.json()
            imgs = data.get("images") or []
            if imgs:
                return self._download(imgs[0]["url"], prompt, "fal")
        return f"[Vision Error] Fal: {last or 'no model succeeded'}"

    # ----------------------------------------------------------
    # Ideogram
    # ----------------------------------------------------------
    def _gen_ideogram(self, prompt, w, h):
        key = self.keys["ideogram"]
        if not key:
            return "[Vision Error] Ideogram: no key."
        # Ideogram uses multipart
        files = {
            "prompt": (None, prompt),
            "aspect_ratio": (None, "16x9" if w >= h else "9x16"),
            "model": (None, "V_2"),
        }
        try:
            r = requests.post(
                "https://api.ideogram.ai/generate",
                headers={"Api-Key": key},
                files=files, timeout=90,
            )
        except Exception as e:
            return f"[Vision Error] Ideogram: {type(e).__name__}"
        if r.status_code == 402:
            return "[Vision Error] Ideogram: no credits."
        if r.status_code >= 300:
            return f"[Vision Error] Ideogram HTTP {r.status_code}: {r.text[:100]}"
        data = r.json()
        items = data.get("data") or []
        if items:
            return self._download(items[0]["url"], prompt, "ideogram")
        return "[Vision Error] Ideogram: no image returned."

    # ----------------------------------------------------------
    # Clipdrop
    # ----------------------------------------------------------
    def _gen_clipdrop(self, prompt, w, h):
        key = self.keys["clipdrop"]
        if not key:
            return "[Vision Error] Clipdrop: no key."
        try:
            r = requests.post(
                "https://clipdrop-api.co/text-to-image/v1",
                headers={"x-api-key": key},
                files={"prompt": (None, prompt)},
                timeout=90,
            )
        except Exception as e:
            return f"[Vision Error] Clipdrop: {type(e).__name__}"
        if r.status_code == 402:
            return "[Vision Error] Clipdrop: out of credits."
        if r.status_code >= 300:
            return f"[Vision Error] Clipdrop HTTP {r.status_code}"
        ct = r.headers.get("content-type", "")
        if not ct.startswith("image"):
            return f"[Vision Error] Clipdrop: {ct}"
        return self._save(r.content, prompt, "clipdrop")

    # ----------------------------------------------------------
    # DeepAI
    # ----------------------------------------------------------
    def _gen_deepai(self, prompt, w, h):
        key = self.keys["deepai"]
        if not key:
            return "[Vision Error] DeepAI: no key."
        try:
            r = requests.post(
                "https://api.deepai.org/api/text2img",
                data={"text": prompt},
                headers={"api-key": key},
                timeout=60,
            )
        except Exception as e:
            return f"[Vision Error] DeepAI: {type(e).__name__}"
        if r.status_code >= 300:
            return f"[Vision Error] DeepAI HTTP {r.status_code}"
        j = r.json()
        u = j.get("output_url")
        if not u:
            return "[Vision Error] DeepAI: no output_url."
        return self._download(u, prompt, "deepai")

    # ----------------------------------------------------------
    # Pollinations (with API key if present)
    # ----------------------------------------------------------
    def _gen_pollinations(self, prompt, w, h, seed):
        q = urllib.parse.quote(prompt)
        url = self.POLLINATIONS_URL.format(prompt=q, width=w, height=h, seed=seed)
        headers = {}
        key = self.keys.get("pollinations")
        if key:
            # Pollinations accepts the key as a Bearer token or a query param.
            headers["Authorization"] = f"Bearer {key}"
        logger.info("[Vision] Pollinations %s", url)
        try:
            r = requests.get(url, headers=headers, timeout=120)
        except Exception as e:
            return f"[Vision Error] Pollinations: {type(e).__name__}"
        if r.status_code == 402:
            # retry with the key as a query param
            if key and "token=" not in url:
                sep = "&" if "?" in url else "?"
                r = requests.get(f"{url}{sep}token={key}",
                                 headers=headers, timeout=120)
        if r.status_code >= 300:
            return f"[Vision Error] Pollinations HTTP {r.status_code}"
        ct = r.headers.get("content-type", "")
        if not ct.startswith("image"):
            return f"[Vision Error] Pollinations content-type {ct}"
        return self._save(r.content, prompt, "pollinations")

    # ----------------------------------------------------------
    # Describe (local Ollama moondream)
    # ----------------------------------------------------------
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
            return f"[Vision Error] ollama HTTP {r.status_code}"
        except Exception as e:
            return f"[Vision Error] ollama: {e}"
'''
(root / "core" / "plugins" / "vision_plugin.py").write_text(vis_src, encoding="utf-8")
print("[ok] rewrote vision_plugin.py")

import py_compile
try:
    py_compile.compile(str(root / "core" / "plugins" / "vision_plugin.py"),
                       doraise=True)
    print("[ok] vision_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

# ============================================================
# 2. Patch video_plugin.py — mark Replicate 402 more clearly,
#    and try Spaces fallback for free video
# ============================================================
vp = root / "core" / "plugins" / "video_plugin.py"
src = vp.read_text(encoding="utf-8")

# Replace the top-level error message again (in case the last patch missed it)
old_final_msg_pattern = '''            f"[Video Error] All video backends failed.\\n"'''
if old_final_msg_pattern in src:
    src = src.replace(old_final_msg_pattern,
                      '''            f"[Video Error] All video backends failed.\\n"''', 1)

# Insert a Replicate 402 handler that gives a clear message
old_402 = 'return "[Video Error] Replicate: prepaid credit exhausted."'
new_402 = ('return ("[Video Error] Replicate account has no credit. '
           'Top up at replicate.com/account/billing, or use a different '
           'video backend.")')
if old_402 in src:
    src = src.replace(old_402, new_402, 1)
    print("[ok] video: clearer Replicate-402 message")
else:
    print("[warn] video: 402 handler not replaced")

vp.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(vp), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] video_plugin.py: {e}")
    raise SystemExit(1)

print()
print("=" * 72)
print("  DONE.")
print("=" * 72)
print("Restart launcher. Test these one at a time:")
print()
print('  > generate image of a dancing baby')
print('    (priority: Replicate -> Fal -> Ideogram -> Clipdrop -> DeepAI -> Pollinations)')
print()
print('  > generate image of a dancing baby backend=fal')
print('    (forces Fal.ai specifically)')
print()
print('  > generate image of a dancing baby backend=pollinations')
print('    (uses your POLLINATIONS_API_KEY now)')
print()
print('  > generate video of a dancing baby')
print('    (Replicate will 402 unless you add credit; that is an account issue)')
print()
print("If you want FREE video generation, the honest path is:")
print("  1. Add ~$10 credit to Replicate (replicate.com/account/billing)")
print("     -> MiniMax Hailuo, Kling 1.6, LTX all unlock")
print("  2. Or run text-to-video locally on a GPU box (needs 16GB+ VRAM)")
print("  3. Or use HuggingFace Spaces manually (browser-only, not API)")