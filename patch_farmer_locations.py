from pathlib import Path

p = Path("agents/farmer_digest_agent.py")
src = p.read_text(encoding="utf-8")

if "from agents.locations import resolve_location" in src:
    print("already patched")
    raise SystemExit(0)

# Add import
needle = "from agents.llm import get_llm"
if needle not in src:
    print("import anchor not found")
    raise SystemExit(1)
src = src.replace(
    needle,
    needle + "\nfrom agents.locations import resolve_location, known_towns",
    1,
)

# Patch compose_brief to resolve the location
old_sig = '''    async def compose_brief(
        self,
        location: str = "Nakuru",
        latitude: float = -0.3031,
        longitude: float = 36.0800,
        crops: str = "maize milk beans",
        topic: str = "agriculture",
    ) -> str:'''

new_sig = '''    async def compose_brief(
        self,
        location: str = "Nakuru",
        latitude: float = None,
        longitude: float = None,
        crops: str = "maize milk beans",
        topic: str = "agriculture",
    ) -> str:
        # Resolve location -> coordinates if not supplied
        if latitude is None or longitude is None:
            hit = resolve_location(location)
            if hit is not None:
                latitude, longitude, location = hit
            else:
                latitude = latitude if latitude is not None else -0.3031
                longitude = longitude if longitude is not None else 36.0800'''

if old_sig not in src:
    print("compose_brief signature anchor not found")
    raise SystemExit(1)
src = src.replace(old_sig, new_sig, 1)

p.write_text(src, encoding="utf-8")
print("farmer_digest_agent now resolves any Kenyan town")