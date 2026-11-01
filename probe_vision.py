"""probe_vision.py - direct HTTP probes against each vision backend.

Prints the exact response (status + body) for fal and ideogram so we can
see why they are being skipped.
"""
import json
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
except Exception:
    pass

try:
    import requests
except ImportError:
    print("pip install requests")
    raise SystemExit(1)


def hdr(s):
    print()
    print("=" * 66)
    print("  " + s)
    print("=" * 66)


# ---------------- FAL ----------------
hdr("FAL.AI")

fal_key = (os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY") or "").strip()
print(f"  key present: {bool(fal_key)}  ({fal_key[:8]}...{fal_key[-4:]})")
print(f"  len: {len(fal_key)}")
print()

# Fal keys can use two different auth header styles. Try both.
fal_models = [
    "fal-ai/flux/schnell",
    "fal-ai/flux/dev",
    "fal-ai/any-llm",
]
auth_styles = [
    ("Key",   {"Authorization": f"Key {fal_key}"}),
    ("Bearer", {"Authorization": f"Bearer {fal_key}"}),
]
for style, auth_h in auth_styles:
    for model in fal_models[:1]:   # just first model per style
        url = f"https://fal.run/{model}"
        payload = {"prompt": "a red apple", "image_size": {"width": 256, "height": 256}}
        print(f"  POST {url}")
        print(f"    auth: {style}")
        try:
            r = requests.post(url, headers={**auth_h, "Content-Type": "application/json"},
                              json=payload, timeout=30)
            print(f"    status: {r.status_code}")
            body = r.text[:400]
            print(f"    body: {body}")
        except Exception as e:
            print(f"    exception: {type(e).__name__}: {e}")

# ---------------- IDEOGRAM ----------------
hdr("IDEOGRAM")

id_key = os.getenv("IDEOGRAM_API_KEY", "").strip()
print(f"  key present: {bool(id_key)}  ({id_key[:8]}...{id_key[-4:]})")
print(f"  len: {len(id_key)}")
print()

# Ideogram v2 endpoint — try both possible URLs
ideo_attempts = [
    ("https://api.ideogram.ai/generate",
     {"Api-Key": id_key},
     {"prompt": "a red apple",
      "aspect_ratio": "1x1",
      "model": "V_2"}),
    ("https://api.ideogram.ai/generate",
     {"Api-Key": id_key},
     {"prompt": "a red apple",
      "aspect_ratio": "1x1",
      "model": "V_2",
      "magic_prompt_option": "AUTO"}),
]
for i, (url, headers, body) in enumerate(ideo_attempts, 1):
    print(f"  attempt {i}: POST {url}")
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        print(f"    status: {r.status_code}")
        print(f"    body: {r.text[:400]}")
    except Exception as e:
        print(f"    exception: {type(e).__name__}: {e}")

# ---------------- CLIPDROP (known working) ----------------
hdr("CLIPDROP (baseline — known to work)")

cd_key = os.getenv("CLIPDROP_API_KEY", "").strip()
print(f"  key present: {bool(cd_key)}")
try:
    r = requests.post(
        "https://clipdrop-api.co/text-to-image/v1",
        headers={"x-api-key": cd_key},
        files={"prompt": (None, "a red apple")},
        timeout=30,
    )
    print(f"  status: {r.status_code}")
    print(f"  content-type: {r.headers.get('content-type', '')}")
    print(f"  size: {len(r.content)} bytes")
except Exception as e:
    print(f"  exception: {type(e).__name__}: {e}")

# ---------------- POLLINATIONS (baseline) ----------------
hdr("POLLINATIONS (baseline — known to work)")
try:
    r = requests.get(
        "https://image.pollinations.ai/prompt/a%20red%20apple"
        "?width=256&height=256&nologo=true",
        timeout=60,
    )
    print(f"  status: {r.status_code}")
    print(f"  content-type: {r.headers.get('content-type', '')}")
    print(f"  size: {len(r.content)} bytes")
except Exception as e:
    print(f"  exception: {type(e).__name__}: {e}")

print()
print("DONE. Paste this entire output.")
