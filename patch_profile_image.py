import json
from pathlib import Path

p = Path("config/agent_profiles.json")
cfg = json.loads(p.read_text(encoding="utf-8"))

# Add image_analysis + analyze_image to every profile that should have it
for profile_name in ("farm", "dev", "work", "personal"):
    if profile_name not in cfg["profiles"]:
        continue
    agents = cfg["profiles"][profile_name]["agents"]
    if "*" in agents:
        continue  # 'all' profile has everything
    for alias in ("image_analysis", "analyze_image"):
        if alias not in agents:
            agents.append(alias)
    print(f"  {profile_name}: added image_analysis + analyze_image")

p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print("Updated config/agent_profiles.json")