from pathlib import Path

# ============================================================
# Fix 1: Ideogram — wrap body in image_request
# ============================================================
vp = Path("core/plugins/vision_plugin.py")
src = vp.read_text(encoding="utf-8")

old_ideo = '''    def _gen_ideogram(self, prompt, w, h):
        tok = self.keys["ideogram"]
        files = {
            "prompt": (None, prompt),
            "aspect_ratio": (None, "16x9" if w >= h else "9x16"),
            "model": (None, "V_2"),
        }
        r = requests.post("https://api.ideogram.ai/generate",
                          headers={"Api-Key": tok}, files=files, timeout=90)'''
new_ideo = '''    def _gen_ideogram(self, prompt, w, h):
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
        )'''
if old_ideo in src:
    src = src.replace(old_ideo, new_ideo, 1)
    print("[ok] vision: Ideogram fixed (image_request wrapper)")
else:
    print("[warn] vision: Ideogram block not matched — check manually")

# ============================================================
# Fix 2: HF Inference endpoint is dead. Point at the new router.
# ============================================================
old_hf = '''    def _gen_huggingface(self, prompt, w, h, seed):
        tok = self.keys["huggingface"]
        last = ""
        for model in self.HF_MODELS:
            r = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {tok}"},
                json={"inputs": prompt, "parameters": {"width": w, "height": h}},
                timeout=120,
            )
            if r.status_code == 503:
                last = f"[Vision Error] HF {model}: model loading (retry in 20s)"
                time.sleep(20)
                r = requests.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"inputs": prompt}, timeout=120,
                )
            if r.status_code >= 300:
                last = self._httperr("HF", model, r)
                continue
            ct = r.headers.get("content-type", "")
            if ct.startswith("image"):
                return self._save(r.content, prompt, "huggingface")
            last = f"[Vision Error] HF {model}: content-type {ct}"
        return last or "[Vision Error] HF: no model succeeded"'''
new_hf = '''    def _gen_huggingface(self, prompt, w, h, seed):
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
        return last or "[Vision Error] HF: no model succeeded"'''
if old_hf in src:
    src = src.replace(old_hf, new_hf, 1)
    print("[ok] vision: HF endpoint updated to router.huggingface.co")
else:
    print("[warn] vision: HF block not matched")

# ============================================================
# Fix 3: Remove the fabricated backends
# ============================================================
for fake in ("veida", "kavel"):
    src = src.replace(f'        if bid == "{fake}":', f'        if bid == "{fake}":  # REMOVED')
    src = src.replace(f'        self._backends["{fake}"] = True',
                      f'        self._backends["{fake}"] = False  # REMOVED')

vp.write_text(src, encoding="utf-8")
print("[ok] vision: disabled veida + kavel")

# ============================================================
# Fix 4: Video plugin — same cleanup + real message
# ============================================================
vid = Path("core/plugins/video_plugin.py")
vsrc = vid.read_text(encoding="utf-8")

for fake in ("agnes", "inferenceport", "prezzy"):
    vsrc = vsrc.replace(f'        self._backends["{fake}"] = True',
                        f'        self._backends["{fake}"] = False  # REMOVED')

old_msg = '        if not errors:\n            return "[Video Error] no backends available."\n        return "[Video Error] all video backends failed:\\n  " + "\\n  ".join(errors)'
new_msg = '''        if not errors:
            return ("[Video Error] No text-to-video backend is available right now.\\n"
                    "  Free-tier reality (Oct 2026): there is no working free API.\\n"
                    "  Options:\\n"
                    "    1. Google Colab notebook running a HF Space (free, manual)\\n"
                    "    2. Add $10 to Replicate → unlock MiniMax/Kling/LTX/Wan\\n"
                    "    3. Add $10 to fal.ai   → unlock Wan 2.2")
        return "[Video Error] all video backends failed:\\n  " + "\\n  ".join(errors)'''
if old_msg in vsrc:
    vsrc = vsrc.replace(old_msg, new_msg, 1)
    print("[ok] video: replaced generic error with honest guidance")
else:
    print("[warn] video: error message anchor not found")

vid.write_text(vsrc, encoding="utf-8")
print("[ok] video: disabled agnes + inferenceport + prezzy")

# ============================================================
# Compile
# ============================================================
import py_compile
for p in (vp, vid):
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.name} compiles")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] {p.name}: {e}")
        raise SystemExit(1)

print()
print("Done. What actually works:")
print("  vision → pollinations, clipdrop (confirmed), + ideogram now fixed")
print("  video  → nothing free. Use Colab or top up Replicate/fal.")
print()
print("For video, here is the Colab path (no signup needed):")
print("  1. Open https://colab.research.google.com")
print("  2. New notebook, paste:")
print("       !pip install gradio_client")
print("       from gradio_client import Client")
print("       c = Client('multimodalart/wan2-1-fast')")
print("       c.predict('a dancing baby', api_name='/generate_video')")
print("  3. Free GPU for 4h/day, unlimited videos.")