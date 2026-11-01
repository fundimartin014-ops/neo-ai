from pathlib import Path

probe = r'''"""probe_backends.py - one-shot diagnostic for video/vision backends."""
import os, re, json
from pathlib import Path

print("=" * 72)
print("  1. ENVIRONMENT KEYS (loaded via load_dotenv)")
print("=" * 72)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
    print("[ok] loaded .env")
except Exception as e:
    print(f"[warn] dotenv load failed: {e}")

keys = [
    "HF_TOKEN", "HUGGINGFACE_API_KEY", "REPLICATE_API_TOKEN",
    "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY", "GROQ_API_KEY",
    "POLLINATIONS_API_KEY", "STABILITY_API_KEY",
    "FAL_API_KEY", "FAL_KEY",
    "TOGETHER_API_KEY", "FIREWORKS_API_KEY",
    "MISTRAL_API_KEY", "CLIPDROP_API_KEY", "IDEOGRAM_API_KEY",
    "DEEPAI_API_KEY", "AI_HORDE_API_KEY", "MOONSHOT_API_KEY",
    "RUNWAY_API_KEY", "LUMA_API_KEY", "PIKA_API_KEY",
]
env_text = Path(".env").read_text(encoding="utf-8") if Path(".env").exists() else ""
for k in keys:
    v = os.getenv(k, "").strip()
    if v:
        print(f"  {k:28} loaded     {v[:8]}...{v[-4:]} ({len(v)} ch)")
        continue
    m = re.search(rf"^{k}\s*=\s*(.+)$", env_text, re.MULTILINE)
    if m:
        raw = m.group(1).strip().strip("'\"")
        print(f"  {k:28} in .env    {raw[:8]}...{raw[-4:]} ({len(raw)} ch)  [NOT exported to os.environ]")
    else:
        print(f"  {k:28} MISSING")

print()
print("=" * 72)
print("  2. VIDEO PLUGIN (core/plugins/video_plugin.py)")
print("=" * 72)
vp = Path("core/plugins/video_plugin.py")
if not vp.exists():
    print("[fail] video_plugin.py not found")
else:
    src = vp.read_text(encoding="utf-8")
    lines = src.splitlines()
    print(f"  [file exists: {len(lines)} lines]")
    print()
    # Print all backend/method/url references
    want = re.compile(
        r"(replicate|huggingface|hf_|hf\.|api-inference|pollinations|fal|"
        r"together|fireworks|stability|deepai|clipdrop|ideogram|ai_horde|"
        r"luma|runway|cogvideo|zeroscope|mochi|minimax|veo|sora|def generate|"
        r"def _run|BACKENDS|backends|model_hint|self\.name|class Plugin)",
        re.I,
    )
    hits = 0
    for i, ln in enumerate(lines, 1):
        if want.search(ln):
            print(f"  {i:5d}: {ln.rstrip()[:110]}")
            hits += 1
    print(f"  [{hits} matching lines]")

print()
print("=" * 72)
print("  3. VISION PLUGIN (core/plugins/vision_plugin.py)")
print("=" * 72)
vis = Path("core/plugins/vision_plugin.py")
if not vis.exists():
    print("[fail] vision_plugin.py not found")
else:
    src = vis.read_text(encoding="utf-8")
    lines = src.splitlines()
    print(f"  [file exists: {len(lines)} lines]")
    print()
    want = re.compile(
        r"(replicate|huggingface|hf_|pollinations|fal|together|fireworks|"
        r"stability|deepai|clipdrop|ideogram|ai_horde|sdxl|flux|def generate|"
        r"def _run|BACKENDS|backends|model_hint|self\.name|class Plugin|"
        r"pollinations\.ai)",
        re.I,
    )
    hits = 0
    for i, ln in enumerate(lines, 1):
        if want.search(ln):
            print(f"  {i:5d}: {ln.rstrip()[:110]}")
            hits += 1
    print(f"  [{hits} matching lines]")

print()
print("=" * 72)
print("  4. LIVE SMOKE TEST")
print("=" * 72)

# Replicate: check /v1/account
try:
    import requests
    tok = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if tok:
        r = requests.get("https://api.replicate.com/v1/account",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=10)
        print(f"  Replicate /account -> {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            print(f"    user: {j.get('username')}, type: {j.get('type')}")
    else:
        print("  Replicate: no token")

    # HF: whoami
    hf = (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY") or "").strip()
    if hf:
        r = requests.get("https://huggingface.co/api/whoami-v2",
                         headers={"Authorization": f"Bearer {hf}"}, timeout=10)
        print(f"  HF whoami -> {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            print(f"    user: {j.get('name')}, plan: {j.get('plan')}")
    else:
        print("  HF: no token")

    # Gemini
    gk = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if gk:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": gk}, timeout=10,
        )
        print(f"  Gemini /models -> {r.status_code}")
    else:
        print("  Gemini: no key")

    # Pollinations (no key)
    r = requests.get("https://image.pollinations.ai/prompt/test?width=64&height=64&nologo=true",
                     timeout=30)
    print(f"  Pollinations image -> {r.status_code} ({len(r.content)} bytes)")

except ImportError:
    print("  [warn] requests not installed; skipping live tests")
except Exception as e:
    print(f"  [warn] smoke test error: {type(e).__name__}: {e}")

print()
print("DONE. Paste this entire output.")
'''
Path("probe_backends.py").write_text(probe, encoding="utf-8")
print("[ok] wrote probe_backends.py")
print("[ok] run it:  python probe_backends.py")