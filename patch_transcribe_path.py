from pathlib import Path

# ---- transcription_agent ----
p = Path("agents/transcription_agent.py")
src = p.read_text(encoding="utf-8")

old = '''        p = Path(audio_path)
        if not p.exists():
            return f"[transcription error] file not found: {audio_path}"'''

new = '''        p = Path(audio_path)
        if not p.is_absolute():
            here = Path(__file__).resolve().parent.parent
            for sub in ("sandbox", "generated_images", ""):
                cand = (here / sub / audio_path) if sub else (here / audio_path)
                if cand.exists():
                    p = cand
                    break
        if not p.exists():
            return f"[transcription error] file not found: {audio_path}"'''

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding="utf-8")
    print("transcription: added path fallback")
else:
    print("transcription: anchor not found")