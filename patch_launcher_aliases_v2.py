from pathlib import Path

p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if '"image_analysis"' in src and "_AGENT_ALIASES" in src:
    print("already present")
    raise SystemExit(0)

old = '''_AGENT_ALIASES = frozenset({
    "search", "summarize", "summary", "farm", "brief", "market",
    "scheduler", "schedule", "web", "fetch", "file", "files",
    "system", "shell", "knowledge", "sentiment", "validate",
    "notify", "notification", "tag", "tagging", "task", "profile", "memory",
})'''

new = '''_AGENT_ALIASES = frozenset({
    "search", "summarize", "summary", "farm", "brief", "market",
    "scheduler", "schedule", "web", "fetch", "file", "files",
    "system", "shell", "knowledge", "sentiment", "validate",
    "notify", "notification", "tag", "tagging", "task", "profile", "memory",
    "disease", "diagnose", "image_analysis", "analyze_image",
})'''

if old not in src:
    print("alias set not found — searching for variations")
    for i, l in enumerate(src.splitlines()):
        if "_AGENT_ALIASES" in l:
            print(f"line {i+1}: {l}")
            # Show next 12 lines
            for j in range(i, min(len(src.splitlines()), i+12)):
                print(f"  {j+1}: {src.splitlines()[j]}")
            break
    raise SystemExit(1)

src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("Added disease + image_analysis to launcher _AGENT_ALIASES")