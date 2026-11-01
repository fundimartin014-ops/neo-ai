from pathlib import Path
p = Path("agents/image_analysis_agent.py")
src = p.read_text(encoding="utf-8")

# 1) Log which file gets resolved
old = '''        resolved, reason = self._resolve_file(image_path)
        if resolved is None:
            return {"backend": "none", "labels": [], "text": "",
                    "error": f"{reason}"}
'''
new = '''        resolved, reason = self._resolve_file(image_path)
        if resolved is None:
            return {"backend": "none", "labels": [], "text": "",
                    "error": f"{reason}"}
        self.logger.info("[image_analysis] analyzing: %s", resolved)
'''
if old in src and "analyzing: %s" not in src:
    src = src.replace(old, new, 1)

# 2) Better message when Ollama returns nothing
old2 = '''        return {
            "backend": f"ollama:{model}",
            "labels": [{"name": desc, "confidence": 100.0, "parents": []}] if desc else [],
            "text": "",
            "error": None,
        }'''
new2 = '''        if not desc:
            return {
                "backend": f"ollama:{model}",
                "labels": [],
                "text": "",
                "error": "Ollama returned an empty description for this image "
                         "(moondream may not recognize the content or the file is corrupt)",
            }

        return {
            "backend": f"ollama:{model}",
            "labels": [{"name": desc, "confidence": 100.0, "parents": []}],
            "text": "",
            "error": None,
        }'''
if old2 in src:
    src = src.replace(old2, new2, 1)

p.write_text(src, encoding="utf-8")
print("Patched: logs resolved file + clearer empty-Ollama message")