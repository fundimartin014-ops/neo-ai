from pathlib import Path
import py_compile, re

vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

# ---- check whether the METHOD DEFINITION exists (not just the call) ----
has_def = re.search(r"^    def _resolve_colab_url\(self\)", src, re.MULTILINE)

if has_def:
    print("[skip] _resolve_colab_url method already defined")
else:
    print("[info] method is missing — inserting now")
    method = '''    def _resolve_colab_url(self):
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

'''
    # Insert right before _gen_colab
    anchor = "    def _gen_colab(self, prompt, sec, w, h):"
    if anchor not in src:
        raise SystemExit("[fail] _gen_colab anchor not found")
    src = src.replace(anchor, method + anchor, 1)

vid.write_text(src, encoding="utf-8")

# ---- final verification ----
check = vid.read_text(encoding="utf-8")
has_def2 = bool(re.search(r"^    def _resolve_colab_url\(self\)", check, re.MULTILINE))
has_call = "self._resolve_colab_url()" in check
print(f"[verify] method definition present: {has_def2}")
print(f"[verify] call site present:         {has_call}")

try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
    raise SystemExit(1)

if not (has_def2 and has_call):
    raise SystemExit("[fail] one of the two pieces still missing")
print("[ok] both definition and call are now in place")