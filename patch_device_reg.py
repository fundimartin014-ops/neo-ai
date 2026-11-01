import json
from pathlib import Path

p = Path("agents/api_server.py")
src = p.read_text(encoding="utf-8")
if "DeviceControlAgent" not in src:
    anchor = "    reg.register(SpeechAgent(bus=bus))"
    if anchor in src:
        src = src.replace(
            anchor,
            anchor + "\n    from agents.device_control_agent import DeviceControlAgent\n"
                     "    reg.register(DeviceControlAgent(bus=bus))",
            1,
        )
        p.write_text(src, encoding="utf-8")
        print("  - registered DeviceControlAgent")

for path_str, alias_block, anchor in [
    ("agents/executor_agent.py",
     '\n    "device": "DeviceControlAgent",\n    "iot": "DeviceControlAgent",',
     '"speak": "SpeechAgent",'),
    ("skills/agents_skill.py",
     '\n    "device":         "DeviceControlAgent",\n    "iot":            "DeviceControlAgent",',
     '"speak":          "SpeechAgent",'),
]:
    pp = Path(path_str)
    s = pp.read_text(encoding="utf-8")
    if '"device"' not in s:
        if anchor in s:
            s = s.replace(anchor, anchor + alias_block, 1)
            pp.write_text(s, encoding="utf-8")
            print(f"  - added device/iot alias in {path_str}")

lp = Path("launcher.py")
lsrc = lp.read_text(encoding="utf-8")
if '"device"' not in lsrc:
    needle = '"speak", "tts",'
    if needle in lsrc:
        lsrc = lsrc.replace(needle, needle + '\n    "device", "iot",', 1)
        lp.write_text(lsrc, encoding="utf-8")
        print("  - added device/iot to launcher _AGENT_ALIASES")

prof = Path("config/agent_profiles.json")
cfg = json.loads(prof.read_text(encoding="utf-8"))
for name in ("farm", "dev", "work", "personal"):
    agents = cfg["profiles"][name]["agents"]
    if "*" in agents:
        continue
    for a in ("device", "iot"):
        if a not in agents:
            agents.append(a)
prof.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("  - added device/iot to all profiles")