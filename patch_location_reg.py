import json
from pathlib import Path

p = Path("agents/api_server.py")
src = p.read_text(encoding="utf-8")
if "LocationAgent" not in src:
    anchor = "    reg.register(TranscriptionAgent(bus=bus))"
    if anchor in src:
        src = src.replace(
            anchor,
            anchor + "\n    from agents.location_agent import LocationAgent\n"
                     "    reg.register(LocationAgent(bus=bus))",
            1,
        )
        p.write_text(src, encoding="utf-8")
        print("  - registered LocationAgent")

for path_str, alias_line, anchor in [
    ("agents/executor_agent.py",
     '\n    "location": "LocationAgent",',
     '"transcribe": "TranscriptionAgent",'),
    ("skills/agents_skill.py",
     '\n    "location":       "LocationAgent",',
     '"transcribe":     "TranscriptionAgent",'),
]:
    pp = Path(path_str)
    s = pp.read_text(encoding="utf-8")
    if '"location"' not in s:
        if anchor in s:
            s = s.replace(anchor, anchor + alias_line, 1)
            pp.write_text(s, encoding="utf-8")
            print(f"  - added location alias in {path_str}")

lp = Path("launcher.py")
lsrc = lp.read_text(encoding="utf-8")
if '"location"' not in lsrc:
    needle = '"transcribe", "voice",'
    if needle in lsrc:
        lsrc = lsrc.replace(needle, needle + '\n    "location",', 1)
        lp.write_text(lsrc, encoding="utf-8")
        print("  - added location to launcher _AGENT_ALIASES")

prof = Path("config/agent_profiles.json")
cfg = json.loads(prof.read_text(encoding="utf-8"))
for name in ("farm", "dev", "work", "personal"):
    agents = cfg["profiles"][name]["agents"]
    if "*" in agents:
        continue
    if "location" not in agents:
        agents.append("location")
prof.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("  - added location to all profiles")