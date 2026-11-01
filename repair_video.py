from pathlib import Path
import re, py_compile

vp = Path("core/plugins/video_plugin.py")
src = vp.read_text(encoding="utf-8")

# Show the corrupted region for the record
lines = src.splitlines()
print("--- lines 55..85 (before repair) ---")
for i in range(54, min(85, len(lines))):
    print(f"  {i+1:4d}: {lines[i]!r}")

# Replace the whole _check_backends method with a clean version
new_method = '''    def _check_backends(self):
        """Probe each backend once. Failures are logged, not fatal."""
        self._backends["pollinations"] = True

        # Replicate — /v1/account returns 200 for any valid token
        if self.keys.get("replicate"):
            try:
                r = requests.get(
                    "https://api.replicate.com/v1/account",
                    headers={"Authorization": f"Bearer {self.keys['replicate']}"},
                    timeout=8,
                )
                self._backends["replicate"] = (r.status_code == 200)
            except Exception as e:
                print(f"[Video] Replicate probe failed: {e}")
                self._backends["replicate"] = False
        else:
            self._backends["replicate"] = False

        # HuggingFace — whoami-v2 works with any valid token.
        # We mark it available; per-model availability is checked at call time.
        if self.keys.get("huggingface"):
            try:
                r = requests.get(
                    "https://huggingface.co/api/whoami-v2",
                    headers={"Authorization": f"Bearer {self.keys['huggingface']}"},
                    timeout=8,
                )
                self._backends["huggingface"] = (r.status_code == 200)
            except Exception as e:
                print(f"[Video] HF probe failed: {e}")
                self._backends["huggingface"] = False
        else:
            self._backends["huggingface"] = False

        # Gemini — models list
        if self.keys.get("gemini"):
            try:
                r = requests.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": self.keys["gemini"]}, timeout=8,
                )
                self._backends["gemini"] = (r.status_code == 200)
            except Exception:
                self._backends["gemini"] = False
        else:
            self._backends["gemini"] = False

        # Ollama vision (moondream)
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            models = [m.get("name", "") for m in r.json().get("models", [])]
            self._backends["ollama_vision"] = any("moondream" in m for m in models)
        except Exception:
            self._backends["ollama_vision"] = False

        # ffmpeg for frame extraction
        import shutil
        self._backends["ffmpeg"] = shutil.which("ffmpeg") is not None

        active = [k for k, v in self._backends.items() if v]
        print(f"[Video] Active backends ({len(active)}): {', '.join(active)}")
'''

# Find and replace the method body
pat = re.compile(
    r"    def _check_backends\(self\):.*?(?=\n    def )",
    re.DOTALL,
)
m = pat.search(src)
if not m:
    raise SystemExit("[fail] _check_backends not found")

src = src[:m.start()] + new_method + src[m.end():]
vp.write_text(src, encoding="utf-8")
print("\n[ok] rewrote _check_backends")

try:
    py_compile.compile(str(vp), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
    # show around the reported line
    m = re.search(r"line (\d+)", str(e))
    if m:
        ln = int(m.group(1))
        new_lines = Path("core/plugins/video_plugin.py").read_text(encoding="utf-8").splitlines()
        for i in range(max(0, ln-4), min(len(new_lines), ln+4)):
            print(f"  {i+1:4d}: {new_lines[i]!r}")
    raise SystemExit(1)

# Also validate vision_plugin (it was written but never compiled because the previous script aborted early)
vis = Path("core/plugins/vision_plugin.py")
if vis.exists():
    try:
        py_compile.compile(str(vis), doraise=True)
        print("[ok] vision_plugin.py compiles")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] vision_plugin.py: {e}")
        raise SystemExit(1)

print()
print("=" * 72)
print("  Both plugins now compile.")
print("=" * 72)
print("Restart launcher, then:")
print('  > generate image of a dancing baby')
print('  > generate image of a dancing baby backend=ideogram')
print('  > generate video of a dancing baby')