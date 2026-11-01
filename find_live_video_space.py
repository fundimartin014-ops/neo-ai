#!/usr/bin/env python3
"""find_live_video_space.py -- probe a list of HF Spaces, report which are live."""
import io, sys, contextlib
from pathlib import Path

SPACES = [
    "zerogpu-aoti/wan2-2-fp8da-aoti-faster",
    "vaibhavpandeyvpz/wan2.2-text-image-to-video",
    "rahul7star/Wan-2.2-5B",
    "zerogpu-aoti/wan2-2-fp8da-aoti",
    "multimodalart/wan-2-2-first-last-frame",
    "akhaliq/LTX-2.5-workflow",
]

OUT = Path(__file__).parent / "space_scan.txt"
lines = []
live = []

try:
    from gradio_client import Client
except ImportError:
    print("ERROR: gradio_client not installed")
    sys.exit(1)

for space in SPACES:
    header = "=" * 70 + chr(10) + "SPACE: " + space
    print(header)
    lines.append(header)
    try:
        client = Client(space, verbose=False)
        print("  STATUS: LIVE")
        lines.append("  STATUS: LIVE")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                client.view_api()
            schema = buf.getvalue()
            lines.append(schema)
        except Exception as e:
            msg = "  SCHEMA ERROR: " + str(e)[:300]
            print(msg); lines.append(msg)
        live.append(space)
    except Exception as e:
        msg = "  STATUS: DEAD -> " + type(e).__name__ + ": " + str(e)[:200]
        print(msg); lines.append(msg)
    lines.append("")

OUT.write_text(chr(10).join(lines), encoding="utf-8")
print()
print("=" * 70)
print("LIVE SPACES:", len(live))
for s in live:
    print("  -", s)
print("Full schema dump: " + str(OUT))
if not live:
    print("No live Spaces from this batch. We try a different batch.")