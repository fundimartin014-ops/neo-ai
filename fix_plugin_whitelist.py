from pathlib import Path

p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

# The block our earlier patch inserted (indented under the plugin-mapping loop)
old = '''            logger.info(f"[Launcher] Plugin mapped: {name}")
            # Background plugins get a start() call
            if hasattr(p, "start") and callable(getattr(p, "start")):
                try:
                    p.start()
                except Exception as _e:
                    logger.warning("[Launcher] %s.start() failed: %s", name, _e)'''

new = '''            logger.info(f"[Launcher] Plugin mapped: {name}")
            # Only these plugins run in the background. Everything else
            # uses only run() (called earlier in the startup-hooks loop).
            _BACKGROUND_PLUGINS = {"farm_scheduler_plugin", "irrigation_alert_plugin"}
            if name in _BACKGROUND_PLUGINS and hasattr(p, "start") and callable(getattr(p, "start")):
                try:
                    p.start()
                except Exception as _e:
                    logger.warning("[Launcher] %s.start() failed: %s", name, _e)'''

if old not in src:
    # Try the version without a body inside try (in case the file differs)
    old_alt = '''            logger.info(f"[Launcher] Plugin mapped: {name}")
            # Background plugins get a start() call
            if hasattr(p, "start") and callable(getattr(p, "start")):
                try:
                    pass
                except Exception as _e:
                    logger.warning("[Launcher] %s.start() failed: %s", name, _e)'''
    if old_alt in src:
        old = old_alt
    else:
        print("anchor not found — dumping 5 lines around 'Plugin mapped'")
        for i, l in enumerate(src.splitlines()):
            if "Plugin mapped" in l:
                for j in range(max(0, i-1), min(len(src.splitlines()), i+10)):
                    print(f"  {j+1}: {src.splitlines()[j]}")
                break
        raise SystemExit(1)

src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("Whitelisted background plugins — voice_trainer will no longer auto-start")