from pathlib import Path

# api_server.py
p = Path("agents/api_server.py")
src = p.read_text(encoding="utf-8")
if "TranscriptionAgent" not in src:
    anchor = "    reg.register(ImageAnalysisAgent(bus=bus))"
    if anchor in src:
        src = src.replace(
            anchor,
            anchor + "\n    from agents.transcription_agent import TranscriptionAgent\n"
                     "    reg.register(TranscriptionAgent(bus=bus))",
            1,
        )
        p.write_text(src, encoding="utf-8")
        print("  - registered TranscriptionAgent")

# executor alias
ex = Path("agents/executor_agent.py")
exsrc = ex.read_text(encoding="utf-8")
if '"transcribe": "TranscriptionAgent"' not in exsrc:
    needle = '"image_analysis": "ImageAnalysisAgent",'
    if needle in exsrc:
        exsrc = exsrc.replace(
            needle,
            needle + '\n    "transcribe": "TranscriptionAgent",\n'
                     '    "voice": "TranscriptionAgent",',
            1,
        )
        ex.write_text(exsrc, encoding="utf-8")
        print("  - added transcribe alias in executor")

# agents_skill ALIASES
sk = Path("skills/agents_skill.py")
sksrc = sk.read_text(encoding="utf-8")
if '"transcribe":' not in sksrc:
    needle = '"image_analysis": "ImageAnalysisAgent",'
    if needle in sksrc:
        sksrc = sksrc.replace(
            needle,
            needle + '\n    "transcribe":     "TranscriptionAgent",\n'
                     '    "voice":          "TranscriptionAgent",',
            1,
        )
        sk.write_text(sksrc, encoding="utf-8")
        print("  - added transcribe to agents_skill")

# launcher _AGENT_ALIASES
lp = Path("launcher.py")
lsrc = lp.read_text(encoding="utf-8")
if '"transcribe"' not in lsrc:
    needle = '"disease", "diagnose", "image_analysis", "analyze_image",'
    if needle in lsrc:
        lsrc = lsrc.replace(
            needle,
            '"disease", "diagnose", "image_analysis", "analyze_image",\n'
            '    "transcribe", "voice",',
            1,
        )
        lp.write_text(lsrc, encoding="utf-8")
        print("  - added transcribe to launcher _AGENT_ALIASES")

# profiles
import json
prof = Path("config/agent_profiles.json")
cfg = json.loads(prof.read_text(encoding="utf-8"))
for name in ("farm", "dev", "work", "personal"):
    agents = cfg["profiles"][name]["agents"]
    if "*" in agents:
        continue
    for alias in ("transcribe", "voice"):
        if alias not in agents:
            agents.append(alias)
prof.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("  - added transcribe/voice to all profiles")