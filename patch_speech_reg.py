import json
from pathlib import Path

# api_server
p = Path("agents/api_server.py")
src = p.read_text(encoding="utf-8")
if "SpeechAgent" not in src:
    anchor = "    reg.register(LocationAgent(bus=bus))"
    if anchor in src:
        src = src.replace(
            anchor,
            anchor + "\n    from agents.speech_agent import SpeechAgent\n"
                     "    reg.register(SpeechAgent(bus=bus))",
            1,
        )
        p.write_text(src, encoding="utf-8")
        print("  - registered SpeechAgent")

# executor + agents_skill
for path_str, alias_block, anchor in [
    ("agents/executor_agent.py",
     '\n    "speak": "SpeechAgent",\n    "tts": "SpeechAgent",',
     '"location": "LocationAgent",'),
    ("skills/agents_skill.py",
     '\n    "speak":          "SpeechAgent",\n    "tts":            "SpeechAgent",',
     '"location":       "LocationAgent",'),
]:
    pp = Path(path_str)
    s = pp.read_text(encoding="utf-8")
    if '"speak"' not in s:
        if anchor in s:
            s = s.replace(anchor, anchor + alias_block, 1)
            pp.write_text(s, encoding="utf-8")
            print(f"  - added speak/tts alias in {path_str}")

# launcher aliases
lp = Path("launcher.py")
lsrc = lp.read_text(encoding="utf-8")
if '"speak"' not in lsrc:
    needle = '"location",'
    if needle in lsrc:
        lsrc = lsrc.replace(needle, needle + '\n    "speak", "tts",', 1)
        lp.write_text(lsrc, encoding="utf-8")
        print("  - added speak/tts to launcher _AGENT_ALIASES")

# profiles
prof = Path("config/agent_profiles.json")
cfg = json.loads(prof.read_text(encoding="utf-8"))
for name in ("farm", "dev", "work", "personal"):
    agents = cfg["profiles"][name]["agents"]
    if "*" in agents:
        continue
    for a in ("speak", "tts"):
        if a not in agents:
            agents.append(a)
prof.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("  - added speak/tts to all profiles")