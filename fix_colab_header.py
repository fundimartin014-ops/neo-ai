from pathlib import Path
import py_compile, re

vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

# Replace the entire _gen_colab with a version that sends ngrok headers
new_method = '''    def _gen_colab(self, prompt, sec, w, h):
        """POST to the user-run Colab notebook (Wan 2.1 Fast on HF Spaces)."""
        base = self.keys.get("colab", "").rstrip("/")
        if not base:
            return "[Video Error] Colab: COLAB_VIDEO_URL not set"
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

'''

# Replace any existing _gen_colab (from "def _gen_colab" up to next "    def ")
pat = re.compile(r"    def _gen_colab\(self.*?(?=    def )", re.DOTALL)
if pat.search(src):
    src = pat.sub(new_method, src, count=1)
    print("[ok] replaced _gen_colab (with ngrok header + health check)")
else:
    # Insert fresh before _call
    anchor = "    def _call(self, bid, prompt, sec, w, h, seed):"
    if anchor not in src:
        raise SystemExit("[fail] neither _gen_colab nor _call found")
    src = src.replace(anchor, new_method + anchor, 1)
    print("[ok] inserted _gen_colab before _call")

vid.write_text(src, encoding="utf-8")

try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    raise SystemExit(1)