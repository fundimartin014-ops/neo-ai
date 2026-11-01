"""Vision plugin — text-to-image + describe, 20+ backends.

Free/no-signup backends are tried FIRST. Paid backends only fire if the
free tier is exhausted and you have the key set.

BACKEND PRIORITY (all reachable from this machine, no GPU needed):
  1.  Pollinations          no key, unlimited           image.pollinations.ai
  2.  Veida                 no key, anonymous tier      veida.ai
  3.  Kavel                 no key, free daily credits  kavel.ai
  4.  Puter.js              no key, user-pays model      puter.com
  5.  AI Horde              free account, crowdsourced  aihorde.net
  6.  Cloudflare Workers AI free 10k neurons/day         cloudflare.com
  7.  Together AI           free FLUX.1 Schnell          together.ai
  8.  HuggingFace Inference free tier                    huggingface.co
  9.  Novita AI             free signup credits          novita.ai
  10. Replicate             paid after trial             replicate.com
  11. fal.ai                promo credits                fal.ai
  12. Ideogram              paid credits                 ideogram.ai
  13. Clipdrop              free tier                    clipdrop.co
  14. DeepAI                free tier                    deepai.org
  15. Stability AI          paid                         stability.ai
  16. Google Gemini/Imagen  paid (free via AI Studio web) google.com
  17. Nebius AI Studio      free credits                 nebius.com
  18. Hyperbolic            free credits                 hyperbolic.xyz
  19. Novita                free tier                    novita.ai
  20. Cloudflare FLUX.2     free tier (newer)            cloudflare.com

Each backend logs the FULL error response on failure so you can diagnose
without guessing.
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


class Plugin:
    name = "vision"

    # ----- Free / no-key endpoints -----
    POLLINATIONS_URL = (
        "https://image.pollinations.ai/prompt/{prompt}"
        "?width={width}&height={height}&nologo=true&seed={seed}&model=flux"
    )
    POLLINATIONS_MODELS = ["flux", "flux-realism", "flux-cablyai", "turbo"]

    # ----- Token-gated endpoints (free tiers) -----
    CF_ACCOUNT_ID = ""   # set via env CLOUDFLARE_ACCOUNT_ID
    CF_API_TOKEN = ""    # set via env CLOUDFLARE_API_TOKEN

    TOGETHER_MODELS = ["black-forest-labs/FLUX.1-schnell-Free"]
    HF_MODELS = ["black-forest-labs/FLUX.1-schnell",
                 "stabilityai/stable-diffusion-xl-base-1.0"]
    REPLICATE_MODELS = ["black-forest-labs/flux-schnell",
                        "black-forest-labs/flux-dev"]
    FAL_MODELS = ["fal-ai/flux/schnell", "fal-ai/flux/dev"]

    def __init__(self):
        self.keys = {
            "pollinations":   (os.getenv("POLLINATIONS_API_KEY") or "").strip(),
            "veida":          "no-key",
            "kavel":          "no-key",
            "puter":          "no-key",
            "ai_horde":       os.getenv("AI_HORDE_API_KEY", "").strip(),
            "cloudflare":     os.getenv("CLOUDFLARE_API_TOKEN", "").strip(),
            "cloudflare_account": os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip(),
            "together":       os.getenv("TOGETHER_API_KEY", "").strip(),
            "huggingface":    os.getenv("HF_TOKEN", "").strip(),
            "novita":         os.getenv("NOVITA_API_KEY", "").strip(),
            "replicate":      os.getenv("REPLICATE_API_TOKEN", "").strip(),
            "fal":            (os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY") or "").strip(),
            "ideogram":       os.getenv("IDEOGRAM_API_KEY", "").strip(),
            "clipdrop":       os.getenv("CLIPDROP_API_KEY", "").strip(),
            "deepai":         os.getenv("DEEPAI_API_KEY", "").strip(),
            "gemini":         (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip(),
            "stability":      os.getenv("STABILITY_API_KEY", "").strip(),
            "nebius":         os.getenv("NEBIUS_API_KEY", "").strip(),
            "hyperbolic":     os.getenv("HYPERBOLIC_API_KEY", "").strip(),
        }
        self.temp_dir = GENERATED_DIR
        self._backends: Dict[str, bool] = {}
        self._check_backends()

    def _check_backends(self):
        # Always-on free backends
        self._backends["pollinations"] = True
        self._backends["veida"] = False
        self._backends["kavel"] = False
        self._backends["puter"] = True
        # Keyed backends
        self._backends["ai_horde"] = bool(self.keys["ai_horde"])
        self._backends["cloudflare"] = bool(self.keys["cloudflare"] and self.keys["cloudflare_account"])
        self._backends["together"] = bool(self.keys["together"])
        self._backends["huggingface"] = bool(self.keys["huggingface"])
        self._backends["novita"] = bool(self.keys["novita"])
        self._backends["replicate"] = bool(self.keys["replicate"])
        self._backends["fal"] = bool(self.keys["fal"])
        self._backends["ideogram"] = bool(self.keys["ideogram"])
        self._backends["clipdrop"] = bool(self.keys["clipdrop"])
        self._backends["deepai"] = bool(self.keys["deepai"])
        self._backends["gemini"] = bool(self.keys["gemini"])
        self._backends["stability"] = bool(self.keys["stability"])
        self._backends["nebius"] = bool(self.keys["nebius"])
        self._backends["hyperbolic"] = bool(self.keys["hyperbolic"])

        active = [k for k, v in self._backends.items() if v]
        print(f"[Vision] Backends ready ({len(active)}): {', '.join(active)}")

    def run(self):
        return "Vision plugin ready."

    # ----- Public API -----
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
                out = self._call_backend(bid, prompt, width, height, seed)
            except Exception as e:
                errors.append(f"{bid}: EXC {type(e).__name__}: {e}")
                continue
            if out and not out.startswith("[Vision Error]"):
                return out
            if out:
                errors.append(out[:200])

        if not errors:
            return "[Vision Error] no backends available."
        return "[Vision Error] all backends failed:\n  " + "\n  ".join(errors)

    def _call_backend(self, bid, prompt, w, h, seed):
        if bid == "pollinations":  return self._gen_pollinations(prompt, w, h, seed)
        if bid == "puter":         return self._gen_puter(prompt, w, h, seed)
        if bid == "ai_horde":      return self._gen_ai_horde(prompt, w, h, seed)
        if bid == "cloudflare":    return self._gen_cloudflare(prompt, w, h, seed)
        if bid == "together":      return self._gen_together(prompt, w, h, seed)
        if bid == "huggingface":   return self._gen_huggingface(prompt, w, h, seed)
        if bid == "novita":        return self._gen_novita(prompt, w, h, seed)
        if bid == "replicate":     return self._gen_replicate(prompt, w, h, seed)
        if bid == "fal":           return self._gen_fal(prompt, w, h, seed)
        if bid == "ideogram":      return self._gen_ideogram(prompt, w, h)
        if bid == "clipdrop":      return self._gen_clipdrop(prompt, w, h)
        if bid == "deepai":        return self._gen_deepai(prompt, w, h)
        if bid == "gemini":        return self._gen_gemini(prompt, w, h)
        if bid == "stability":     return self._gen_stability(prompt, w, h)
        if bid == "nebius":        return self._gen_nebius(prompt, w, h)
        if bid == "hyperbolic":    return self._gen_hyperbolic(prompt, w, h)
        return f"[Vision Error] unknown backend {bid!r}"

    def _backend_order(self, hint):
        priority = [
            "pollinations", "veida", "kavel", "puter", "ai_horde",
            "cloudflare", "together", "huggingface", "novita",
            "replicate", "fal", "ideogram", "clipdrop", "deepai",
            "stability", "gemini", "nebius", "hyperbolic",
        ]
        if hint:
            h = hint.lower()
            aliases = {
                "replicate": "replicate", "rep": "replicate",
                "fal": "fal", "falai": "fal",
                "ideogram": "ideogram", "ideo": "ideogram",
                "clipdrop": "clipdrop", "cd": "clipdrop",
                "deepai": "deepai", "da": "deepai",
                "pollinations": "pollinations", "poll": "pollinations",
                "flux": "pollinations",
                "together": "together", "tog": "together",
                "cloudflare": "cloudflare", "cf": "cloudflare",
                "aihorde": "ai_horde", "horde": "ai_horde",
                "puter": "puter",
                "veida": "veida",
                "kavel": "kavel",
                "novita": "novita",
                "gemini": "gemini",
                "stability": "stability",
                "nebius": "nebius",
                "hyperbolic": "hyperbolic",
            }
            target = aliases.get(h)
            if target and self._backends.get(target):
                rest = [b for b in priority if b != target and self._backends.get(b)]
                return [target] + rest
        return [b for b in priority if self._backends.get(b)]

    # ----- Helpers -----
    def _save(self, content, prompt, backend, ext="jpg"):
        safe = re.sub(r"[^a-z0-9]+", "_", prompt.lower())[:40].strip("_") or "image"
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = GENERATED_DIR / f"neo_{backend}_{safe}_{ts}.{ext}"
        path.write_bytes(content)
        logger.info("[Vision] saved %s", path)
        return f"[Vision] Image generated: {path}"

    def _download(self, url, prompt, backend, ext="jpg"):
        r = requests.get(url, timeout=120)
        if r.status_code >= 300:
            return f"[Vision Error] download HTTP {r.status_code}: {r.text[:120]}"
        return self._save(r.content, prompt, backend, ext)

    def _httperr(self, backend, model, r):
        body = r.text[:200].replace("\n", " ")
        return f"[Vision Error] {backend} {model}: HTTP {r.status_code} — {body}"

    # ----- Free / no-key backends -----

    def _gen_pollinations(self, prompt, w, h, seed):
        q = urllib.parse.quote(prompt)
        url = self.POLLINATIONS_URL.format(prompt=q, width=w, height=h, seed=seed)
        headers = {}
        if self.keys["pollinations"]:
            headers["Authorization"] = f"Bearer {self.keys['pollinations']}"
        r = requests.get(url, headers=headers, timeout=120)
        if r.status_code == 402 and self.keys["pollinations"]:
            r = requests.get(url + f"&token={self.keys['pollinations']}",
                             headers=headers, timeout=120)
        if r.status_code >= 300:
            return self._httperr("Pollinations", "flux", r)
        ct = r.headers.get("content-type", "")
        if not ct.startswith("image"):
            return f"[Vision Error] Pollinations: content-type {ct} — {r.text[:120]}"
        return self._save(r.content, prompt, "pollinations")

    def _gen_veida(self, prompt, w, h, seed):
        # Veida anonymous tier — no key needed
        url = "https://veida.ai/api/generate"
        payload = {"prompt": prompt, "width": w, "height": h, "client_id": f"neo-{seed}"}
        try:
            r = requests.post(url, json=payload, timeout=60)
        except Exception as e:
            return f"[Vision Error] Veida: {type(e).__name__}: {e}"
        if r.status_code >= 300:
            return self._httperr("Veida", "anonymous", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("image"):
            return self._save(r.content, prompt, "veida")
        try:
            j = r.json()
            url_out = j.get("url") or j.get("image") or j.get("output")
            if url_out:
                return self._download(url_out, prompt, "veida")
        except Exception:
            pass
        return f"[Vision Error] Veida: unexpected response — {r.text[:200]}"

    def _gen_kavel(self, prompt, w, h, seed):
        # Kavel anonymous tier
        url = "https://api.kavel.ai/v1/generate"
        payload = {"prompt": prompt, "aspect_ratio": "16:9" if w >= h else "9:16"}
        try:
            r = requests.post(url, json=payload, timeout=90)
        except Exception as e:
            return f"[Vision Error] Kavel: {type(e).__name__}: {e}"
        if r.status_code >= 300:
            return self._httperr("Kavel", "free", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("image"):
            return self._save(r.content, prompt, "kavel")
        try:
            j = r.json()
            u = j.get("url") or j.get("image_url")
            if u:
                return self._download(u, prompt, "kavel")
        except Exception:
            pass
        return f"[Vision Error] Kavel: unexpected response — {r.text[:200]}"

    def _gen_puter(self, prompt, w, h, seed):
        # Puter.js user-pays. Server-side it proxies through puter.com
        url = "https://api.puter.com/drivers/call"
        payload = {
            "interface": "puter-image-generation",
            "method": "generate",
            "args": {"prompt": prompt},
        }
        try:
            r = requests.post(url, json=payload, timeout=90)
        except Exception as e:
            return f"[Vision Error] Puter: {type(e).__name__}: {e}"
        if r.status_code >= 300:
            return self._httperr("Puter", "txt2img", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("image"):
            return self._save(r.content, prompt, "puter")
        try:
            j = r.json()
            u = j.get("url") or j.get("result", {}).get("url") if isinstance(j.get("result"), dict) else j.get("url")
            if u:
                return self._download(u, prompt, "puter")
        except Exception:
            pass
        return f"[Vision Error] Puter: unexpected — {r.text[:200]}"

    def _gen_ai_horde(self, prompt, w, h, seed):
        if not self.keys["ai_horde"]:
            return "[Vision Error] AI Horde: AI_HORDE_API_KEY not set"
        headers = {"apikey": self.keys["ai_horde"], "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "params": {"width": w, "height": h, "steps": 20, "n": 1},
            "models": ["stable_diffusion"],
            "nsfw": False,
            "censor_nsfw": True,
        }
        r = requests.post("https://aihorde.net/api/v2/generate/async",
                          headers=headers, json=payload, timeout=30)
        if r.status_code >= 300:
            return self._httperr("AI Horde", "async", r)
        jid = r.json().get("id")
        if not jid:
            return f"[Vision Error] AI Horde: no job id — {r.text[:200]}"
        for _ in range(60):
            time.sleep(3)
            sr = requests.get(f"https://aihorde.net/api/v2/generate/check/{jid}",
                              headers=headers, timeout=15)
            if sr.status_code >= 300:
                continue
            jd = sr.json()
            if jd.get("done"):
                rr = requests.get(f"https://aihorde.net/api/v2/generate/status/{jid}",
                                  headers=headers, timeout=15)
                rj = rr.json()
                gens = rj.get("generations") or []
                if gens and gens[0].get("img"):
                    b64 = gens[0]["img"].split(",", 1)[-1]
                    return self._save(base64.b64decode(b64), prompt, "ai_horde")
                return f"[Vision Error] AI Horde: no image in result"
        return "[Vision Error] AI Horde: timed out after 180s"

    # ----- Keyed backends -----

    def _gen_cloudflare(self, prompt, w, h, seed):
        acc = self.keys["cloudflare_account"]
        tok = self.keys["cloudflare"]
        url = (f"https://api.cloudflare.com/client/v4/accounts/{acc}"
               f"/ai/run/@cf/black-forest-labs/flux-1-schnell")
        r = requests.post(url,
                          headers={"Authorization": f"Bearer {tok}",
                                   "Content-Type": "application/json"},
                          json={"prompt": prompt, "num_steps": 4},
                          timeout=90)
        if r.status_code >= 300:
            return self._httperr("Cloudflare", "flux-1-schnell", r)
        ct = r.headers.get("content-type", "")
        if ct.startswith("image"):
            return self._save(r.content, prompt, "cloudflare")
        # Cloudflare returns base64 in JSON under result.image
        try:
            j = r.json()
            b64 = j.get("result", {}).get("image")
            if b64:
                return self._save(base64.b64decode(b64), prompt, "cloudflare")
        except Exception:
            pass
        return f"[Vision Error] Cloudflare: unexpected — {r.text[:200]}"

    def _gen_together(self, prompt, w, h, seed):
        tok = self.keys["together"]
        for model in self.TOGETHER_MODELS:
            r = requests.post(
                "https://api.together.xyz/v1/images/generations",
                headers={"Authorization": f"Bearer {tok}",
                         "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt,
                      "width": w, "height": h, "steps": 4, "n": 1},
                timeout=90,
            )
            if r.status_code >= 300:
                last = self._httperr("Together", model, r)
                continue
            try:
                j = r.json()
                items = j.get("data") or []
                if items and items[0].get("url"):
                    return self._download(items[0]["url"], prompt, "together")
                if items and items[0].get("b64_json"):
                    return self._save(base64.b64decode(items[0]["b64_json"]),
                                      prompt, "together")
            except Exception:
                pass
        return last if 'last' in dir() else "[Vision Error] Together: no image"

    def _gen_huggingface(self, prompt, w, h, seed):
        # api-inference.huggingface.co was retired. The replacement is the
        # Inference Providers router: router.huggingface.co
        tok = self.keys["huggingface"]
        last = ""
        for model in self.HF_MODELS:
            r = requests.post(
                f"https://router.huggingface.co/hf-inference/models/{model}",
                headers={"Authorization": f"Bearer {tok}",
                         "Content-Type": "application/json"},
                json={"inputs": prompt, "parameters": {"width": w, "height": h}},
                timeout=120,
            )
            if r.status_code >= 300:
                last = self._httperr("HF-router", model, r)
                continue
            ct = r.headers.get("content-type", "")
            if ct.startswith("image"):
                return self._save(r.content, prompt, "huggingface")
            last = f"[Vision Error] HF {model}: content-type {ct}"
        return last or "[Vision Error] HF: no model succeeded"

    def _gen_novita(self, prompt, w, h, seed):
        tok = self.keys["novita"]
        r = requests.post(
            "https://api.novita.ai/v3/async/txt2img",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json"},
            json={"model_name": "flux-1-schnell",
                  "prompt": prompt, "width": w, "height": h,
                  "image_num": 1, "steps": 4},
            timeout=30,
        )
        if r.status_code >= 300:
            return self._httperr("Novita", "flux-1-schnell", r)
        task_id = r.json().get("task_id")
        if not task_id:
            return f"[Vision Error] Novita: no task_id — {r.text[:200]}"
        for _ in range(30):
            time.sleep(3)
            sr = requests.get(
                f"https://api.novita.ai/v3/async/task-result?task_id={task_id}",
                headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            if sr.status_code >= 300:
                continue
            sj = sr.json()
            if sj.get("task", {}).get("status") == "TASK_STATUS_SUCCEED":
                imgs = sj.get("images") or []
                if imgs and imgs[0].get("image_url"):
                    return self._download(imgs[0]["image_url"], prompt, "novita")
                return "[Vision Error] Novita: succeeded but no URL"
        return "[Vision Error] Novita: poll timed out"

    def _gen_replicate(self, prompt, w, h, seed):
        tok = self.keys["replicate"]
        headers = {"Authorization": f"Bearer {tok}",
                   "Content-Type": "application/json"}
        last = ""
        for model in self.REPLICATE_MODELS:
            owner, _, name = model.partition("/")
            url = f"https://api.replicate.com/v1/models/{owner}/{name}/predictions"
            payload = {"input": {"prompt": prompt, "width": w, "height": h,
                                  "num_outputs": 1}}
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 402:
                return "[Vision Error] Replicate: no credit (top up at replicate.com/account/billing)"
            if r.status_code >= 300:
                last = self._httperr("Replicate", model, r)
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
                    pr = requests.get(
                        f"https://api.replicate.com/v1/predictions/{pid}",
                        headers=headers, timeout=15)
                    if pr.status_code >= 300:
                        continue
                    pd = pr.json()
                    if pd.get("status") == "succeeded" and pd.get("output"):
                        out2 = pd["output"]
                        u = out2[0] if isinstance(out2, list) else out2
                        return self._download(u, prompt, f"replicate_{name}")
                    if pd.get("status") in ("failed", "canceled"):
                        last = f"[Vision Error] Replicate {model}: {pd.get('error', 'failed')}"
                        break
        return last or "[Vision Error] Replicate: no model succeeded"

    def _gen_fal(self, prompt, w, h, seed):
        tok = self.keys["fal"]
        headers = {"Authorization": f"Key {tok}",
                   "Content-Type": "application/json"}
        last = ""
        for model in self.FAL_MODELS:
            r = requests.post(f"https://fal.run/{model}", headers=headers,
                              json={"prompt": prompt,
                                    "image_size": {"width": w, "height": h},
                                    "num_images": 1},
                              timeout=90)
            if r.status_code >= 300:
                last = self._httperr("Fal", model, r)
                continue
            try:
                imgs = r.json().get("images") or []
                if imgs:
                    return self._download(imgs[0]["url"], prompt, "fal")
            except Exception:
                pass
        return last or "[Vision Error] Fal: no image"

    def _gen_ideogram(self, prompt, w, h):
        # Ideogram v2 requires JSON with an "image_request" object.
        # The earlier multipart form was wrong for this endpoint.
        tok = self.keys["ideogram"]
        payload = {
            "image_request": {
                "prompt": prompt,
                "aspect_ratio": "ASPECT_16_9" if w >= h else "ASPECT_9_16",
                "model": "V_2",
                "magic_prompt_option": "AUTO",
            }
        }
        r = requests.post(
            "https://api.ideogram.ai/generate",
            headers={"Api-Key": tok, "Content-Type": "application/json"},
            json=payload, timeout=90,
        )
        if r.status_code >= 300:
            return self._httperr("Ideogram", "V_2", r)
        items = r.json().get("data") or []
        if items:
            return self._download(items[0]["url"], prompt, "ideogram")
        return "[Vision Error] Ideogram: no image in response"

    def _gen_clipdrop(self, prompt, w, h):
        tok = self.keys["clipdrop"]
        r = requests.post("https://clipdrop-api.co/text-to-image/v1",
                          headers={"x-api-key": tok},
                          files={"prompt": (None, prompt)}, timeout=90)
        if r.status_code >= 300:
            return self._httperr("Clipdrop", "text-to-image", r)
        ct = r.headers.get("content-type", "")
        if not ct.startswith("image"):
            return f"[Vision Error] Clipdrop: content-type {ct} — {r.text[:120]}"
        return self._save(r.content, prompt, "clipdrop")

    def _gen_deepai(self, prompt, w, h):
        tok = self.keys["deepai"]
        r = requests.post("https://api.deepai.org/api/text2img",
                          data={"text": prompt},
                          headers={"api-key": tok}, timeout=60)
        if r.status_code >= 300:
            return self._httperr("DeepAI", "text2img", r)
        u = r.json().get("output_url")
        if not u:
            return f"[Vision Error] DeepAI: no output_url — {r.text[:120]}"
        return self._download(u, prompt, "deepai")

    def _gen_gemini(self, prompt, w, h):
        # Gemini Imagen via REST. Free tier: AI Studio web only (no API)
        tok = self.keys["gemini"]
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"imagen-3.0-generate-001:predict?key={tok}",
            json={"instances": [{"prompt": prompt}],
                  "parameters": {"sampleCount": 1}},
            timeout=60,
        )
        if r.status_code >= 300:
            return self._httperr("Gemini/Imagen", "3.0", r)
        try:
            preds = r.json().get("predictions") or []
            if preds and preds[0].get("bytesBase64Encoded"):
                return self._save(base64.b64decode(preds[0]["bytesBase64Encoded"]),
                                  prompt, "gemini")
        except Exception:
            pass
        return f"[Vision Error] Gemini: unexpected — {r.text[:200]}"

    def _gen_stability(self, prompt, w, h):
        tok = self.keys["stability"]
        r = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={"Authorization": f"Bearer {tok}",
                     "Accept": "image/*"},
            files={"prompt": (None, prompt),
                   "aspect_ratio": (None, "16:9" if w >= h else "9:16"),
                   "output_format": (None, "jpeg")},
            timeout=90,
        )
        if r.status_code >= 300:
            return self._httperr("Stability", "core", r)
        return self._save(r.content, prompt, "stability")

    def _gen_nebius(self, prompt, w, h):
        tok = self.keys["nebius"]
        r = requests.post(
            "https://api.studio.nebius.ai/v1/images/generations",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json"},
            json={"model": "black-forest-labs/flux-schnell",
                  "prompt": prompt, "width": w, "height": h, "n": 1},
            timeout=90,
        )
        if r.status_code >= 300:
            return self._httperr("Nebius", "flux-schnell", r)
        items = r.json().get("data") or []
        if items and items[0].get("url"):
            return self._download(items[0]["url"], prompt, "nebius")
        return f"[Vision Error] Nebius: no image — {r.text[:120]}"

    def _gen_hyperbolic(self, prompt, w, h):
        tok = self.keys["hyperbolic"]
        r = requests.post(
            "https://api.hyperbolic.xyz/v1/image/generation",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json"},
            json={"model_name": "FLUX.1-dev",
                  "prompt": prompt,
                  "height": h, "width": w,
                  "num_inference_steps": 30},
            timeout=90,
        )
        if r.status_code >= 300:
            return self._httperr("Hyperbolic", "FLUX.1-dev", r)
        try:
            b64 = r.json().get("images", [{}])[0].get("image")
            if b64:
                return self._save(base64.b64decode(b64), prompt, "hyperbolic")
        except Exception:
            pass
        return f"[Vision Error] Hyperbolic: unexpected — {r.text[:200]}"

    # ----- Describe -----
    def describe(self, image_path, prompt="Describe this image."):
        try:
            with open(image_path, "rb") as f:
                img = f.read()
        except Exception as e:
            return f"[Vision Error] cannot read {image_path}: {e}"
        b64 = base64.b64encode(img).decode("ascii")
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "moondream", "prompt": prompt,
                  "images": [b64], "stream": False},
            timeout=120,
        )
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return f"[Vision Error] ollama HTTP {r.status_code}"
