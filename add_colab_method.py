from pathlib import Path
import py_compile, re

vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

# --- 1. strip any partial _gen_colab ---
src = re.sub(
    r"    def _gen_colab\(self.*?\n(?:    .*\n|\n)*?(?=    def )",
    "",
    src, flags=re.DOTALL,
)

# --- 2. insert _gen_colab before _call ---
method = '''    def _gen_colab(self, prompt, sec, w, h):
        """POST to the user-run Colab notebook (Wan 2.1 Fast on HF Spaces)."""
        base = self.keys.get("colab", "").rstrip("/")
        if not base:
            return "[Video Error] Colab: COLAB_VIDEO_URL not set"
        try:
            r = requests.post(
                f"{base}/generate",
                json={"prompt": prompt, "seconds": sec},
                timeout=600,
            )
        except Exception as e:
            return f"[Video Error] Colab: {type(e).__name__}: {e}"
        if r.status_code >= 300:
            return f"[Video Error] Colab HTTP {r.status_code}: {r.text[:200]}"
        try:
            j = r.json()
        except Exception:
            return "[Video Error] Colab: non-JSON response"
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

anchor = "    def _call(self, bid, prompt, sec, w, h, seed):"
if anchor not in src:
    raise SystemExit("[fail] _call anchor not found")
src = src.replace(anchor, method + anchor, 1)
print("[ok] inserted _gen_colab before _call")

# --- 3. rewrite priority list with colab first ---
m = re.search(r"        priority = \[\n(.*?)\n        \]", src, re.DOTALL)
if m:
    items = re.findall(r'"([^"]+)"', m.group(1))
    disabled = {"agnes", "inferenceport", "prezzy"}
    ordered = ["colab"] + [x for x in items if x != "colab" and x not in disabled]
    new_body = "            " + ", ".join('"{}"'.format(x) for x in ordered) + ","
    src = src[:m.start()] + "        priority = [\n" + new_body + "\n        ]" + src[m.end():]
    print("[ok] priority list rewritten:", ordered)
else:
    print("[warn] priority list not found")

# --- 4. add colab dispatcher if missing ---
if "self._gen_colab(prompt" not in src:
    da = '        if bid == "puter":'
    if da in src:
        src = src.replace(da, '        if bid == "colab":         return self._gen_colab(prompt, sec, w, h)\n' + da, 1)
        print("[ok] added colab dispatcher")
    else:
        print("[warn] puter anchor missing")
else:
    print("[skip] dispatcher already present")

# --- 5. add colab alias if missing ---
colab_alias = '"colab": "colab"'
if colab_alias not in src:
    aa = '                "puter": "puter",'
    if aa in src:
        src = src.replace(aa, '                "colab": "colab", "colabvideo": "colab",\n' + aa, 1)
        print("[ok] added colab alias")
    else:
        print("[warn] alias anchor missing")
else:
    print("[skip] alias already present")

# --- 6. save + compile ---
vid.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    ln_m = re.search(r"line (\d+)", str(e))
    if ln_m:
        ln = int(ln_m.group(1))
        lines = vid.read_text(encoding="utf-8").splitlines()
        for i in range(max(0, ln-5), min(len(lines), ln+5)):
            print("  {:4d}: {!r}".format(i+1, lines[i]))
    raise SystemExit(1)

# --- 7. sanity ---
check = vid.read_text(encoding="utf-8")
has_method = "def _gen_colab" in check
has_disp   = "self._gen_colab" in check
has_alias  = colab_alias in check
prio_body  = check.split("priority = [")[1].split("]")[0] if "priority = [" in check else ""
has_prio   = "colab" in prio_body
print()
print("Sanity check:")
print("  _gen_colab defined:   ", has_method)
print("  colab in dispatcher:  ", has_disp)
print("  colab alias present:  ", has_alias)
print("  colab in priority:    ", has_prio)