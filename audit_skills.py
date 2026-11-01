from pathlib import Path
import re

root = Path(".").resolve()
skills_dir = root / "skills"
exclude = {".git", "__pycache__", ".venv", "node_modules", "data", "generated_images", "sandbox"}

# 1. every skill module (skip __init__ and agent wrappers, flag separately)
skill_files = sorted(p for p in skills_dir.glob("*.py") if p.name != "__init__.py")
agent_wrappers = [p for p in skill_files if p.stem.startswith("agents_")]
pure_skills    = [p for p in skill_files if not p.stem.startswith("agents_")]

# 2. build the searchable universe: every .py outside skills/
corpus = []
for p in root.rglob("*.py"):
    if any(part in exclude for part in p.parts):
        continue
    if skills_dir in p.parents:
        continue
    try:
        corpus.append((p, p.read_text(encoding="utf-8", errors="ignore")))
    except Exception:
        pass

def refs_to(name: str):
    """Return files that reference the module name."""
    hits = []
    for p, text in corpus:
        # match `import skills.NAME`, `from skills.NAME import`, or `skills.NAME.`
        if re.search(rf"\bskills[\.\s]+{re.escape(name)}\b", text) or \
           re.search(rf"\bfrom\s+skills\s+import\s+{re.escape(name)}\b", text):
            hits.append(p)
    # also look inside skills/ itself (excluding own file) for cross-refs
    for p in skill_files:
        if p.stem == name:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"\b{re.escape(name)}\b", text):
            hits.append(p)
    return hits

print("=" * 72)
print("SKILL WIRING AUDIT")
print("=" * 72)
print()
print(f"agent-wrapper skills : {len(agent_wrappers)}")
print(f"pure skill modules   : {len(pure_skills)}")
print()

def report(label, files):
    print("-" * 72)
    print(label)
    print("-" * 72)
    used, orphan = [], []
    for p in files:
        hits = refs_to(p.stem)
        (used if hits else orphan).append((p, hits))

    print(f"\n  WIRED ({len(used)}):")
    for p, hits in used:
        who = ", ".join(str(h.relative_to(root)) for h in hits[:3])
        more = "" if len(hits) <= 3 else f" (+{len(hits)-3})"
        print(f"    ✓ {p.name:<40s}  ← {who}{more}")

    print(f"\n  ORPHANED ({len(orphan)}):")
    for p, _ in orphan:
        print(f"    ✗ {p.name:<40s}  (no references outside itself)")
    print()

report("AGENT-WRAPPER SKILLS (agents_*.py)", agent_wrappers)
report("PURE SKILLS", pure_skills)

# 3. What does the launcher actually load? Look for known entrypoints.
print("=" * 72)
print("LAUNCHER ENTRYPOINTS")
print("=" * 72)
for candidate in ("main.py", "app.py", "server.py", "launcher.py",
                  "run.py", "core/orchestrator.py", "core/router.py",
                  "core/agent_router.py", "core/skill_router.py"):
    p = root / candidate
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="ignore")
        imports_agents_skill  = "agents_skill" in text or "from skills import agents" in text
        imports_select_skill  = "select_skill" in text
        imports_other_skills  = re.findall(r"from\s+skills[\.\s]+(\w+)", text)
        print(f"\n  {candidate}")
        print(f"    agents_skill referenced : {imports_agents_skill}")
        print(f"    select_skill referenced : {imports_select_skill}")
        print(f"    other skills imported   : {sorted(set(imports_other_skills)) or '(none)'}")