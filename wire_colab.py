from pathlib import Path
import py_compile

vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

# 1. Add "colab" to the keyed backends dict
old_keys = '            "huggingface":   os.getenv("HF_TOKEN", "").strip(),'
new_keys = ('            "huggingface":   os.getenv("HF_TOKEN", "").strip(),\n'
            '            "colab":         os.getenv("COLAB_VIDEO_URL", "").strip(),')
if old_keys in src and '"colab"' not in src:
    src = src.replace(old_keys, new_keys, 1)
    print("[ok] added colab key")

# 2. Register availability
old_check = '        self._backends["huggingface"] = bool(self.keys["huggingface"])'
new_check = ('        self._backends["huggingface"] = bool(self.keys["huggingface"])\n'
             '        self._backends["colab"] = bool(self.keys.get("colab"))')
if old_check in src and 'self._backends["colab"]' not in src:
    src = src.replace(old_check, new_check, 1)
    print("[ok] registered colab availability")

# 3. Put colab first in priority order
old_prio = ('        priority = [\n'
            '            "agnes", "inferenceport", "prezzy", "magic_hour", "puter",\n'
            '            "vidu", "seedance", "replicate", "fal", "huggingface",\n'
            '        ]')
new_prio = ('        priority = [\n'
            '            "colab",\n'
            '            "magic_hour", "vidu", "seedance", "puter",\n'
            '            "replicate", "fal", "huggingface",\n'
            '        ]')
if old_prio in src:
    src = src.replace(old_prio, new_prio, 1)
    print("[ok] colab first in priority list")
else:
    print("[warn] priority list not matched")

# 4. Add colab alias
old_alias = '                "agnes": "agnes",'
new_alias = ('                "colab": "colab", "colabvideo": "colab",\n'
             '                "agnes": "agnes",')
if old_alias in src and '"colab": "colab"' not in src:
    src = src.replace(old_alias, new_alias, 1)
    print("[ok] added colab alias")

# 5. Dispatch in _call
old_dispatch = '        if bid == "agnes":         return self._gen_agnes(prompt, sec, w, h, seed)'
new_dispatch = ('        if bid == "colab":         return self._gen_colab(prompt, sec, w, h)\n'
                '        if bid == "agnes":         return self._gen_agnes(prompt, sec, w, h, seed)')
if old_dispatch in src and 'self._gen_colab' not in src:
    src = src.replace(old_dispatch, new_dispatch, 1)
    print("[ok] added colab dispatcher")

# 6. Add the _gen_colab method right before # ----- No-key backends -----
method = '''    def _gen_colab(self, prompt, sec, w, h):
        """POST to the user-run Colab notebook (Wan 2.1 Fast on HF Spaces)."""
        base = self.keys["colab"].rstrip("/")
        try:
            r = requests.post(
                f"{base}/generate",
                json={"prompt": prompt, "seconds": sec},
                timeout=600,   # video gen can take 2-5 min on free Colab
            )
        except Exception as e:
            return f"[Video Error] Colab: {type(e).__name__}: {e}"
        if r.status_code >= 300:
            return f"[Video Error] Colab HTTP {r.status_code}: {r.text[:200]}"
        try:
            j = r.json()
        except Exception:
            return f"[Video Error] Colab: non-JSON response"
        if not j.get("ok"):
            return f"[Video Error] Colab: {j}"
        b64 = j.get("video_b64")
        if not b64:
            return f"[Video Error] Colab: no video_b64 in response"
        try:
            data = base64.b64decode(b64)
        except Exception as e:
            return f"[Video Error] Colab: base64 decode failed: {e}"
        return self._save_video(data, prompt, "colab")

    # ----- No-key backends -----'''

anchor = "    # ----- No-key backends -----"
if anchor in src and "_gen_colab" not in src.split(anchor)[0].rsplit("class", 1)[-1]:
    # crude check — replace only the first occurrence of the anchor inside class
    src = src.replace(anchor, method, 1)
    print("[ok] added _gen_colab method")
else:
    print("[warn] could not add _gen_colab — anchor already used")

vid.write_text(src, encoding="utf-8")

try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

# .env.example
env_ex = Path(".env.example")
existing = env_ex.read_text(encoding="utf-8") if env_ex.exists() else ""
if "COLAB_VIDEO_URL" not in existing:
    env_ex.write_text(existing + """

# ============ Colab video backend ============
# Free text-to-video via Google Colab (Wan 2.1 Fast on an HF Space).
# See docs/COLAB_VIDEO.md for the 3-step setup.
# Paste the ngrok URL printed by the Colab notebook, then restart Neo.
# COLAB_VIDEO_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
""", encoding="utf-8")
    print("[ok] .env.example: added COLAB_VIDEO_URL")

print()
print("=" * 64)
print("  Colab backend wired into Neo's video plugin")
print("=" * 64)
print()
print("To use it:")
print("  1. Run colab_video_server.ipynb in Colab (Runtime -> Run all)")
print("  2. Copy the printed URL into .env:")
print("       COLAB_VIDEO_URL=https://xxxx.ngrok-free.app")
print("  3. Restart launcher")
print("  4. In Neo: generate video of a dancing baby")