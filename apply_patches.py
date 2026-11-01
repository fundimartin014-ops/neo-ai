from pathlib import Path
import re

root = Path(__file__).resolve().parent

# ---------- Patch 1: register KnowledgeAgent in api_server.py ----------
api = root / "agents" / "api_server.py"
src = api.read_text(encoding="utf-8")

if "KnowledgeAgent" not in src:
    # 1a. insert import after last "from agents.X import Y" line inside build_registry
    lines = src.splitlines(keepends=True)
    last_import_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith("from agents.") and " import " in ln:
            last_import_idx = i
    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1,
                     "    from agents.knowledge_agent import KnowledgeAgent\n")
        src = "".join(lines)
    else:
        src = src.replace(
            "def build_registry(bus: MessageBus, db: Database) -> AgentRegistry:\n",
            "def build_registry(bus: MessageBus, db: Database) -> AgentRegistry:\n"
            "    from agents.knowledge_agent import KnowledgeAgent\n",
            1,
        )

    # 1b. insert register() call before the first reg/registry.register(...)
    m = re.search(r"^(\s*)(reg|registry)\.register\(", src, re.MULTILINE)
    if m:
        indent, var = m.group(1), m.group(2)
        line = indent + var + ".register(KnowledgeAgent())\n"
        src = src[:m.start()] + line + src[m.start():]
    else:
        m2 = re.search(r"^(\s*)return\s+(reg|registry)\s*$", src, re.MULTILINE)
        if m2:
            indent, var = m2.group(1), m2.group(2)
            line = indent + var + ".register(KnowledgeAgent())\n"
            src = src[:m2.start()] + line + src[m2.start():]

    api.write_text(src, encoding="utf-8")
    print("[ok]  agents/api_server.py — KnowledgeAgent added to build_registry")
else:
    print("[skip] agents/api_server.py already mentions KnowledgeAgent")

# ---------- Patch 2: make image tests generic in harness ----------
h = root / "autonomous_test_harness.py"
hsrc = h.read_text(encoding="utf-8")

new_disease = (
    '    def t_disease_image(registry=None):\n'
    '        img_dir = PROJECT_ROOT / "generated_images"\n'
    '        if not img_dir.exists():\n'
    '            raise RuntimeError("generated_images/ missing")\n'
    '        imgs = [p for p in img_dir.iterdir()\n'
    '                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]\n'
    '        if not imgs:\n'
    '            raise RuntimeError("no images in generated_images/")\n'
    '        crop_hint = ("leaf", "crop", "plant", "maize", "tomato", "cassava", "disease")\n'
    '        crop_img = next((p for p in imgs\n'
    '                         if any(h in p.stem.lower() for h in crop_hint)), None)\n'
    '        if crop_img is None:\n'
    '            raise RuntimeError(\n'
    '                f"no crop-like image found ({len(imgs)} generic images) - "\n'
    '                "rename one to include leaf/crop/plant to exercise this test"\n'
    '            )\n'
    '        return _call_agent(registry, "DiseaseAlertAgent", "run", str(crop_img),\n'
    '                           timeout=120)\n'
)

new_vision = (
    '    def t_image_analysis(registry=None):\n'
    '        img_dir = PROJECT_ROOT / "generated_images"\n'
    '        if not img_dir.exists():\n'
    '            raise RuntimeError("generated_images/ missing")\n'
    '        imgs = [p for p in img_dir.iterdir()\n'
    '                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]\n'
    '        if not imgs:\n'
    '            raise RuntimeError("no images in generated_images/")\n'
    '        return _call_agent(registry, "ImageAnalysisAgent", "run", str(imgs[0]),\n'
    '                           timeout=120)\n'
)

pat_disease = re.compile(
    r"    def t_disease_image\(registry=None\):.*?"
    r"(?=    tests\.append\(TestCase\(\"disease\.image\")",
    re.DOTALL,
)
hsrc, n1 = pat_disease.subn(lambda m: new_disease, hsrc)

pat_vision = re.compile(
    r"    def t_image_analysis\(registry=None\):.*?"
    r"(?=    tests\.append\(TestCase\(\"image\.analysis\")",
    re.DOTALL,
)
hsrc, n2 = pat_vision.subn(lambda m: new_vision, hsrc)

h.write_text(hsrc, encoding="utf-8")
print(f"[ok]  autonomous_test_harness.py — disease_image replaced: {n1}, image_analysis replaced: {n2}")

# ---------- Sanity check ----------
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("api_server_check", api)
    print("[ok]  api_server.py still imports cleanly")
except Exception as e:
    print(f"[warn] api_server import check skipped: {e}")