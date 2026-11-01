from pathlib import Path
import py_compile, re

vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

# 1. Add NTFY topic to keys dict (right after colab key)
old = '            "colab":         os.getenv("COLAB_VIDEO_URL", "").strip(),'
new = ('            "colab":         os.getenv("COLAB_VIDEO_URL", "").strip(),\n'
       '            "colab_ntfy":    os.getenv("COLAB_NTFY_TOPIC", "").strip(),')
if old in src and '"colab_ntfy"' not in src:
    src = src.replace(old, new, 1)
    print("[ok] added colab_ntfy key")

# 2. Replace _gen_colab's base-resolution line with the resolver call
old_base = '        base = self.keys.get("colab", "").rstrip("/")\n        if not base:\n            return "[Video Error] Colab: COLAB_VIDEO_URL not set"'
new_base = '        base = self._resolve_colab_url()\n        if not base:\n            return "[Video Error] Colab: no URL (set COLAB_VIDEO_URL or COLAB_NTFY_TOPIC)"'
if old_base in src:
    src = src.replace(old_base, new_base, 1)
    print("[ok] _gen_colab now uses _resolve_colab_url()")

# 3. Insert _resolve_colab_url right before _gen_colab
resolver = '''    def _resolve_colab_url(self):
        """Get the Colab tunnel URL from .env, or fetch the latest one from ntfy."""
        # Direct URL wins if set
        direct = (self.keys.get("colab") or "").rstrip("/")
        if direct:
            return direct
        topic = (self.keys.get("colab_ntfy") or "").strip()
        if not topic:
            return ""
        # Cache for 60s to avoid hammering ntfy
        import time as _t
        now = _t.time()
        cached_url, cached_at = getattr(self, "_colab_cache", (None, 0))
        if cached_url and (now - cached_at) < 60:
            return cached_url
        try:
            # Poll the topic once with poll=1 (returns one message, no streaming)
            r = requests.get(
                f"https://ntfy.sh/{topic}/json",
                params={"poll": "1", "since": "1h"},
                timeout=10,
            )
            if r.status_code >= 300:
                return ""
            # Response is newline-delimited JSON objects
            lines = [l for l in r.text.strip().splitlines() if l.strip()]
            for line in reversed(lines):
                try:
                    import json
                    msg = json.loads(line)
                    event = msg.get("event")
                    if event == "message" and msg.get("message"):
                        url = msg["message"].strip()
                        if url.startswith("http"):
                            self._colab_cache = (url, now)
                            return url.rstrip("/")
                except Exception:
                    continue
        except Exception as e:
            print(f"[video] ntfy fetch failed: {type(e).__name__}: {e}")
        return ""

'''
anchor = "    def _gen_colab(self, prompt, sec, w, h):"
if anchor in src and "_resolve_colab_url" not in src:
    src = src.replace(anchor, resolver + anchor, 1)
    print("[ok] inserted _resolve_colab_url")
elif "_resolve_colab_url" in src:
    print("[skip] _resolve_colab_url already present")

vid.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    raise SystemExit(1)

# .env.example
env_ex = Path(".env.example")
existing = env_ex.read_text(encoding="utf-8") if env_ex.exists() else ""
if "COLAB_NTFY_TOPIC" not in existing:
    env_ex.write_text(existing + """

# Colab URL auto-discovery via ntfy.sh
# Set this to the SAME topic used in your Colab notebook cell 5.
# Every time you restart Colab, the new URL is picked up automatically.
# Leave COLAB_VIDEO_URL empty when using this.
# COLAB_NTFY_TOPIC=neo-colab-fundi-9k4m2x
""", encoding="utf-8")
    print("[ok] .env.example updated")