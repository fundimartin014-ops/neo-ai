from pathlib import Path
p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if "_strip_outer_quotes" in src:
    print("already patched")
    raise SystemExit(0)

# Insert a tiny quote-stripper helper before _find_agents_tool
needle = "def _find_agents_tool(agent_core):"
helper = '''def _strip_outer_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("\\"", "'"):
        return s[1:-1].strip()
    return s


'''
if needle not in src:
    print("anchor not found")
    raise SystemExit(1)
src = src.replace(needle, helper + needle, 1)

# In _try_agents_preflight, strip quotes from the payload after the colon
old = '''    head = stripped.split(":", 1)[0].strip().lower()
    if head not in _AGENT_ALIASES:
        return None
    tool = _find_agents_tool(agent_core)
    if tool is None:
        return None
    try:
        if callable(tool):
            result = tool(query=stripped)'''

new = '''    head, _, tail = stripped.partition(":")
    head = head.strip().lower()
    if head not in _AGENT_ALIASES:
        return None
    # Rebuild the query with outer quotes stripped from the payload
    rebuilt = f"{head}: {_strip_outer_quotes(tail)}"
    tool = _find_agents_tool(agent_core)
    if tool is None:
        return None
    try:
        if callable(tool):
            result = tool(query=rebuilt)'''

if old not in src:
    print("preflight anchor not found — inspect _try_agents_preflight manually")
    # Don't fail; helper alone is still useful
else:
    src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
print("Added quote stripping to launcher preflight")