from pathlib import Path

p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if "plugin.start()" in src or "_plugin.start()" in src:
    print("already patched")
    raise SystemExit(0)

# Find the plugin-mapping loop (which iterates over plugins)
needle = "            logger.info(f\"[Launcher] Plugin mapped: {name}\")"
if needle not in src:
    # Try alternate whitespace
    for line in src.splitlines():
        if "Plugin mapped:" in line:
            needle = line
            break
    else:
        print("plugin-mapped anchor not found")
        raise SystemExit(1)

# Insert a start() call right after the logger.info
indent = " " * (len(needle) - len(needle.lstrip()))
addition = (
    needle
    + "\n"
    + indent + "# Background plugins get a start() call\n"
    + indent + "if hasattr(p, \"start\") and callable(getattr(p, \"start\")):\n"
    + indent + "    try:\n"
    + indent + "        p.start()\n"
    + indent + "    except Exception as _e:\n"
    + indent + "        logger.warning(\"[Launcher] %s.start() failed: %s\", name, _e)"
)
src = src.replace(needle, addition, 1)
p.write_text(src, encoding="utf-8")
print("launcher.py will now call .start() on background plugins")