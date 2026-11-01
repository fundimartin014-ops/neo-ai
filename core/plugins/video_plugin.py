"""Video plugin — 10+ text-to-video backends.

Priority (free first):
  1.  Agnes AI          free, no card, no quota      agnes-ai.cn
  2.  InferencePort AI  no key, no signup            inferenceport.ai
  3.  Prezzy Studio     no key, no signup            prexzyapis.com
  4.  Magic Hour        free 400+100/day             magichour.ai
  5.  Puter.js          no key, user-pays            puter.com
  6.  Vidu Q3           free 40 credits/month        vidu.com
  7.  Seedance fast     free 20 calls/month           volcengine.com
  8.  Replicate         paid after credit            replicate.com
  9.  fal.ai            promo credits                fal.ai
  10. HuggingFace       free tier                    huggingface.co

Every backend logs the FULL response on failure.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)
try:
    import requests
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False

GENERATED_DIR = Path("generated_images")
GENERATED_DIR.mkdir(exist_ok=True)


class Plugin:
    name = "video"

    REPLICATE_MODELS = [
        "minimax/hailuo-02",
        "minimax/video-01",
        "kwaivgi/kling-v1.6-standard",
        "wan-video/wan-2.2-t2v-fast",
        "lightricks/ltx-video",
    ]

    def __init__(self):
        self.keys = {
            "agnes":         (os.getenv("AGNES_API_KEY") or "sk-free-builtin").strip(),
            "inferenceport": "no-key",
            "prezzy":        "no-key",
            "magic_hour":    os.getenv("MAGIC_HOUR_API_KEY", "").strip(),
            "puter":         "no-key",
            "vidu":          os.getenv("VIDU_API_KEY", "").strip(),
            "seedance":      os.getenv("VOLCENGINE_API_KEY", "").strip(),
            "replicate":     os.getenv("REPLICATE_API_TOKEN", "").strip(),
            "fal":           (os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY") or "").strip(),
            "huggingface":   os.getenv("HF_TOKEN", "").strip(),
            "colab":         os.getenv("COLAB_VIDEO_URL", "").strip(),
            "colab_ntfy":    os.getenv("COLAB_NTFY_TOPIC", "").strip(),
        }
        self.temp_dir = GENERATED_DIR
        self._backends: Dict[str, bool] = {}
        self._check_backends()

    def _check_backends(self):
        # No-key always-on
        self._backends["agnes"] = False  # REMOVED
        self._backends["inferenceport"] = False  # REMOVED
        self._backends["prezzy"] = False  # REMOVED
        self._backends["puter"] = True
        # Keyed
        self._backends["magic_hour"] = bool(self.keys["magic_hour"])
        self._backends["vidu"] = bool(self.keys["vidu"])
        self._backends["seedance"] = bool(self.keys["seedance"])
        self._backends["replicate"] = bool(self.keys["replicate"])
        self._backends["fal"] = bool(self.keys["fal"])
        self._backends["huggingface"] = bool(self.keys["huggingface"])
        self._backends["colab"] = bool(
            self.keys.get("colab") or self.keys.get("colab_ntfy")
        )
        self._backends["ollama_vision"] = self._probe_ollama()
        self._backends["ffmpeg"] = shutil.which("ffmpeg") is not None

        active = [k for k, v in self._backends.items() if v]
        print(f"[Video] Active backends ({len(active)}): {', '.join(active)}")

    def _probe_ollama(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return any("moondream" in m for m in models)
        except Exception:
            return False

    def run(self):
        return "Video plugin ready."

    def generate(self, prompt, seconds=4, width=1024, height=576, seed=None, model_hint=None):
        if not _HAS_REQ:
            return "[Video Error] requests not installed."
        if not prompt or not prompt.strip():
            return "[Video Error] empty prompt."
        prompt = prompt.strip()
        seed = seed or (int(time.time()) % 1_000_000)

        order = self._backend_order(model_hint)
        errors = []
        for bid in order:
            try:
                out = self._call(bid, prompt, seconds, width, height, seed)
            except Exception as e:
                errors.append(f"{bid}: EXC {type(e).__name__}: {e}")
                continue
            if out and not out.startswith("[Video Error]"):
                return out
            if out:
                errors.append(out[:200])

        if not errors:
            return ("[Video Error] No text-to-video backend is available right now.\n"
                    "  Free-tier reality (Oct 2026): there is no working free API.\n"
                    "  Options:\n"
                    "    1. Google Colab notebook running a HF Space (free, manual)\n"
                    "    2. Add $10 to Replicate → unlock MiniMax/Kling/LTX/Wan\n"
                    "    3. Add $10 to fal.ai   → unlock Wan 2.2")
        return "[Video Error] all video backends failed:\n  " + "\n  ".join(errors)

    def _resolve_colab_url(self):
        """Get the Colab tunnel URL from .env, or fetch the latest from ntfy."""
        direct = (self.keys.get("colab") or "").rstrip("/")
        if direct:
            return direct
        topic = (self.keys.get("colab_ntfy") or "").strip()
        if not topic:
            return ""
        import time as _t
        now = _t.time()
        cached_url, cached_at = getattr(self, "_colab_cache", (None, 0))
        if cached_url and (now - cached_at) < 60:
            return cached_url
        try:
            r = requests.get(
                f"https://ntfy.sh/{topic}/json",
                params={"poll": "1", "since": "1h"},
                timeout=10,
            )
            if r.status_code >= 300:
                return ""
            import json as _json
            for line in reversed(r.text.strip().splitlines()):
                if not line.strip():
                    continue
                try:
                    msg = _json.loads(line)
                except Exception:
                    continue
                if msg.get("event") == "message" and msg.get("message"):
                    url = msg["message"].strip()
                    if url.startswith("http"):
                        url = url.rstrip("/")
                        self._colab_cache = (url, now)
                        return url
        except Exception as e:
            print(f"[video] ntfy fetch failed: {type(e).__name__}: {e}")
        return ""

    def _gen_colab(self, prompt, sec, w, h):
        """POST to the user-run Colab notebook (Wan 2.1 Fast on HF Spaces)."""
        base = self._resolve_colab_url()
        if not base:
            return "[Video Error] Colab: no URL (set COLAB_VIDEO_URL or COLAB_NTFY_TOPIC)"
        # ngrok free tier shows a browser warning page unless this header is
        # present. Send it on both health-check and generate calls.
        headers = {
            "ngrok-skip-browser-warning": "true",
            "User-Agent": "Neo/1.0",
            "Content-Type": "application/json",
        }
        # 1. quick health check to distinguish "not up" from "up but failing"
        try:
            h = requests.get(f"{base}/health", headers=headers, timeout=15)
        except Exception as e:
            return f"[Video Error] Colab: unreachable ({type(e).__name__}: {e})"
        if h.status_code >= 300:
            # Probably still on the ngrok warning page — print a hint
            hint = ""
            if "ngrok" in h.text.lower() or "You are about to visit" in h.text:
                hint = " (ngrok interstitial — header might not be respected)"
            return f"[Video Error] Colab /health HTTP {h.status_code}{hint}: {h.text[:150]}"
        try:
            hj = h.json()
        except Exception:
            return f"[Video Error] Colab /health non-JSON: {h.text[:150]}"
        if not hj.get("ok"):
            return f"[Video Error] Colab /health not ok: {hj}"
        # 2. real generation
        try:
            r = requests.post(
                f"{base}/generate",
                headers=headers,
                json={"prompt": prompt, "seconds": sec},
                timeout=600,
            )
        except Exception as e:
            return f"[Video Error] Colab: generate failed ({type(e).__name__}: {e})"
        if r.status_code >= 300:
            return f"[Video Error] Colab /generate HTTP {r.status_code}: {r.text[:200]}"
        try:
            j = r.json()
        except Exception:
            return "[Video Error] Colab: /generate non-JSON response"
        if not j.get("ok"):
            return f"[Video Error] Colab: {j}"
        b64 = j.get("video_b64")
        if not b64:
            return "[Video Error] Colab: no video_b64 in response"
        try:
            data = base64.b64decode(b64)
        except Exception as e:
            return f"[Video Error] Colab: base64 decode failed: {e}"
        return self._save_video(data, prompt, "colab")

    def _call(self, bid, prompt, sec, w, h, seed):
        if bid == "colab":         return self._gen_colab(prompt, sec, w, h)
        if bid == "agnes":         return self._gen_agnes(prompt, sec, w, h, seed)
        if bid == "inferenceport": return self._gen_inferenceport(prompt, sec, w, h)
        if bid == "prezzy":        return self._gen_prezzy(prompt, sec, w, h)
        if bid == "magic_hour":    return self._gen_magic_hour(prompt, sec, w, h)
        if bid == "puter":         return self._gen_puter(prompt, sec, w, h, seed)
        if bid == "vidu":          return self._gen_vidu(prompt, sec, w, h)
        if bid == "seedance":      return self._gen_seedance(prompt, sec, w, h)
        if bid == "replicate":     return self._gen_replicate(prompt, sec, w, h, seed)
        if bid == "fal":           return self._gen_fal(prompt, sec, w, h)
        if bid == "huggingface":   return self._gen_huggingface(prompt, sec, w, h)
        return f"[Video Error] unknown backend {bid!r}"

    def _backend_order(self, hint):
        priority = [
            "colab", "magic_hour", "vidu", "seedance", "puter", "replicate", "fal", "huggingface",
        ]
        if hint:
            h = hint.lower()
            aliases = {
                "colab": "colab", "colabvideo": "colab",
                "agnes": "agnes",
                "inferenceport": "inferenceport", "ip": "inferenceport",
                "prezzy": "prezzy",
                "magic": "magic_hour", "magichour": "magic_hour",
                "puter": "puter",
                "vidu": "vidu",
                "seedance": "seedance",
                "replicate": "replicate", "rep": "replicate",
                "fal": "fal",
                "hf": "huggingface", "huggingface": "huggingface",
            }
            target = aliases.get(h)
            if target and self._backends.get(target):
                rest = [b for b in priority if b != target and self._backends.get(b)]
                return [target] + rest
        return [b for b in priority if self._backends.get(b)]

    def _save_video(self, content, prompt, backend, ext="mp4"):
        import re
        safe = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_") or "video"
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = GENERATED_DIR / f"neo_{backend}_{safe}_{ts}.{ext}"
        path.write_bytes(content)
        return f"[Video] Video saved: {path} ({len(content)} bytes)"

    def _http_err(self, backend, model, r):
        body = r.text[:250].replace("\n", " ")
        return f"[Video Error] {backend} {model}: HTTP {r.status_code} — {body}"

    # ----- No-key backends -----

    def _gen_agnes(self, prompt, sec, w, h, seed):
        key = self.keys["agnes"]
        r = requests.post(
            "https://apihub.agnes-ai.com/v1/video/generations",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"model": "agnes-video-2.5-flash",
                  "prompt": prompt, "duration": sec},
            timeout=30,
        )
        if r.status_code >= 300:
            return self._http_err("Agnes", "agnes-video-2.5-flash", r)
        j = r.json()
        url = (j.get("data") or [{}])[0].get("url") or j.get("url")
        if not url:
            return f"[Video Error] Agnes: no url — {r.text[:200]}"
        # poll if needed
        for _ in range(60):
            if url:
                rr = requests.get(url, timeout=120)
                if rr.status_code == 200:
                    return self._save_video(rr.content, prompt, "agnes")
            time.sleep(5)
            sr = requests.get(
                f"https://apihub.agnes-ai.com/v1/video/generations/{j.get('id')}",
                headers={"Authorization": f"Bearer {key}"}, timeout=15)
            if sr.status_code == 200:
                sd = sr.json()
                url = (sd.get("data") or [{}])[0].get("url") or sd.get("url")
                if sd.get("status") in ("failed", "error"):
                    return f"[Video Error] Agnes: {sd.get('status')}"
        return "[Video Error] Agnes: timed out"

    def _gen_inferenceport(self, prompt, sec, w, h):
        r = requests.post(
            "https://inferenceport.ai/v1/videos/generations",
            headers={"Content-Type": "application/json"},
            json={"model": "vidu", "prompt": prompt, "duration": sec},
            timeout=90,
        )
        if r.status_code >= 300:
            return self._http_err("InferencePort", "vidu", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("video"):
            return self._save_video(r.content, prompt, "inferenceport")
        try:
            j = r.json()
            u = j.get("url") or (j.get("data") or [{}])[0].get("url")
            if u:
                rr = requests.get(u, timeout=120)
                return self._save_video(rr.content, prompt, "inferenceport")
        except Exception:
            pass
        return f"[Video Error] InferencePort: unexpected — {r.text[:200]}"

    def _gen_prezzy(self, prompt, sec, w, h):
        r = requests.post(
            "https://prexzyapis.com/v1/video/generate",
            headers={"Content-Type": "application/json"},
            json={"prompt": prompt, "duration": sec},
            timeout=120,
        )
        if r.status_code >= 300:
            return self._http_err("Prezzy", "video", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("video"):
            return self._save_video(r.content, prompt, "prezzy")
        try:
            j = r.json()
            u = j.get("url") or j.get("video_url")
            if u:
                rr = requests.get(u, timeout=120)
                return self._save_video(rr.content, prompt, "prezzy")
        except Exception:
            pass
        return f"[Video Error] Prezzy: unexpected — {r.text[:200]}"

    def _gen_puter(self, prompt, sec, w, h, seed):
        r = requests.post(
            "https://api.puter.com/drivers/call",
            json={"interface": "puter-video-generation",
                  "method": "generate",
                  "args": {"prompt": prompt, "duration": sec}},
            timeout=120,
        )
        if r.status_code >= 300:
            return self._http_err("Puter", "video", r)
        try:
            j = r.json()
            u = j.get("url") or (j.get("result") or {}).get("url")
            if u:
                rr = requests.get(u, timeout=120)
                return self._save_video(rr.content, prompt, "puter")
        except Exception:
            pass
        return f"[Video Error] Puter: unexpected — {r.text[:200]}"

    # ----- Keyed backends -----

    def _gen_magic_hour(self, prompt, sec, w, h):
        key = self.keys["magic_hour"]
        r = requests.post(
            "https://api.magichour.ai/v1/text-to-video",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"name": "neo", "end_seconds": sec,
                  "orientation": "landscape",
                  "style": {"prompt": prompt},
                  "model": "ltx-2.5"},
            timeout=30,
        )
        if r.status_code >= 300:
            return self._http_err("MagicHour", "ltx-2.5", r)
        j = r.json()
        jid = j.get("id")
        if not jid:
            return f"[Video Error] MagicHour: no job id — {r.text[:200]}"
        for _ in range(90):
            time.sleep(5)
            sr = requests.get(
                f"https://api.magichour.ai/v1/video-projects/{jid}",
                headers={"Authorization": f"Bearer {key}"}, timeout=15)
            if sr.status_code >= 300:
                continue
            sd = sr.json()
            if sd.get("status") == "complete":
                vurl = sd.get("download", {}).get("url")
                if vurl:
                    rr = requests.get(vurl, timeout=120)
                    return self._save_video(rr.content, prompt, "magic_hour")
                return "[Video Error] MagicHour: complete but no download"
            if sd.get("status") in ("error", "failed"):
                return f"[Video Error] MagicHour: {sd.get('status')} — {str(sd)[:200]}"
        return "[Video Error] MagicHour: timed out"

    def _gen_vidu(self, prompt, sec, w, h):
        key = self.keys["vidu"]
        r = requests.post(
            "https://api.vidu.com/ent/v2/text2video",
            headers={"Authorization": f"Token {key}",
                     "Content-Type": "application/json"},
            json={"model": "viduq1", "prompt": prompt,
                  "duration": sec, "aspect_ratio": "16:9"},
            timeout=30,
        )
        if r.status_code >= 300:
            return self._http_err("Vidu", "viduq1", r)
        j = r.json()
        tid = j.get("task_id")
        if not tid:
            return f"[Video Error] Vidu: no task_id — {r.text[:200]}"
        for _ in range(90):
            time.sleep(5)
            sr = requests.get(
                f"https://api.vidu.com/ent/v2/tasks/{tid}/creations",
                headers={"Authorization": f"Token {key}"}, timeout=15)
            if sr.status_code >= 300:
                continue
            sd = sr.json()
            if sd.get("state") == "success":
                urls = (sd.get("creations") or [{}])[0].get("url")
                if urls:
                    rr = requests.get(urls, timeout=120)
                    return self._save_video(rr.content, prompt, "vidu")
            if sd.get("state") == "failed":
                return f"[Video Error] Vidu: failed — {str(sd)[:200]}"
        return "[Video Error] Vidu: timed out"

    def _gen_seedance(self, prompt, sec, w, h):
        key = self.keys["seedance"]
        r = requests.post(
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"model": "doubao-seedance-2-0-fast-250528",
                  "content": [{"type": "text", "text": prompt}]},
            timeout=30,
        )
        if r.status_code >= 300:
            return self._http_err("Seedance", "fast", r)
        tid = r.json().get("id")
        if not tid:
            return f"[Video Error] Seedance: no task id — {r.text[:200]}"
        for _ in range(60):
            time.sleep(5)
            sr = requests.get(
                f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{tid}",
                headers={"Authorization": f"Bearer {key}"}, timeout=15)
            if sr.status_code >= 300:
                continue
            sd = sr.json()
            if sd.get("status") == "succeeded":
                vurl = (sd.get("content") or {}).get("video_url")
                if vurl:
                    rr = requests.get(vurl, timeout=120)
                    return self._save_video(rr.content, prompt, "seedance")
            if sd.get("status") == "failed":
                return f"[Video Error] Seedance: {sd.get('error', 'failed')}"
        return "[Video Error] Seedance: timed out"

    def _gen_replicate(self, prompt, sec, w, h, seed):
        tok = self.keys["replicate"]
        headers = {"Authorization": f"Bearer {tok}",
                   "Content-Type": "application/json"}
        last = ""
        for model in self.REPLICATE_MODELS:
            owner, _, name = model.partition("/")
            url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
            payload = {"input": {"prompt": prompt, "duration": sec}}
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 402:
                return "[Video Error] Replicate: no credit (replicate.com/account/billing)"
            if r.status_code >= 300:
                last = self._http_err("Replicate", model, r)
                continue
            data = r.json()
            pid = data.get("id")
            if not pid:
                last = f"[Video Error] Replicate {model}: no prediction id"
                continue
            for _ in range(90):
                time.sleep(3)
                pr = requests.get(
                    f"https://api.replicate.com/v1/predictions/{pid}",
                    headers=headers, timeout=15)
                if pr.status_code >= 300:
                    continue
                pd = pr.json()
                if pd.get("status") == "succeeded" and pd.get("output"):
                    out = pd["output"]
                    u = out[0] if isinstance(out, list) else out
                    rr = requests.get(u, timeout=120)
                    return self._save_video(rr.content, prompt, f"replicate_{name}")
                if pd.get("status") in ("failed", "canceled"):
                    last = f"[Video Error] Replicate {model}: {pd.get('error', 'failed')}"
                    break
        return last or "[Video Error] Replicate: no model succeeded"

    def _gen_fal(self, prompt, sec, w, h):
        tok = self.keys["fal"]
        r = requests.post(
            "https://fal.run/fal-ai/wan/v2.2/text-to-video",
            headers={"Authorization": f"Key {tok}",
                     "Content-Type": "application/json"},
            json={"prompt": prompt, "num_frames": sec * 16},
            timeout=90,
        )
        if r.status_code >= 300:
            return self._http_err("Fal", "wan-2.2", r)
        try:
            v = r.json().get("video") or r.json().get("data", {}).get("video")
            if v and v.get("url"):
                rr = requests.get(v["url"], timeout=120)
                return self._save_video(rr.content, prompt, "fal")
        except Exception:
            pass
        return f"[Video Error] Fal: unexpected — {r.text[:200]}"

    def _gen_huggingface(self, prompt, sec, w, h):
        # HF Inference does not host text-to-video; this uses a Space
        tok = self.keys["huggingface"]
        r = requests.post(
            "https://api-inference.huggingface.co/models/damo-vilab/text-to-video-ms-1.7b",
            headers={"Authorization": f"Bearer {tok}"},
            json={"inputs": prompt}, timeout=120,
        )
        if r.status_code >= 300:
            return self._http_err("HF", "text-to-video-ms", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("video"):
            return self._save_video(r.content, prompt, "huggingface")
        return f"[Video Error] HF: content-type {ct}"
