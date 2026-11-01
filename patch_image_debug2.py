from pathlib import Path
p = Path("agents/image_analysis_agent.py")
src = p.read_text(encoding="utf-8")

# Simpler prompt
old_prompt = '''                        "prompt": (
                            "Describe what is in this photo in one sentence. "
                            "Then, if there is any visible text, copy it verbatim."
                        ),'''
new_prompt = '''                        "prompt": "Describe this image.",'''
if old_prompt in src:
    src = src.replace(old_prompt, new_prompt, 1)

# Log raw JSON before parsing
old_parse = '''                if r.status_code != 200:
                    detail = r.text[:200]
                    return {"backend": "ollama", "labels": [], "text": "",
                            "error": f"ollama HTTP {r.status_code}: {detail}"}
                desc = r.json().get("response", "").strip()'''
new_parse = '''                if r.status_code != 200:
                    detail = r.text[:200]
                    return {"backend": "ollama", "labels": [], "text": "",
                            "error": f"ollama HTTP {r.status_code}: {detail}"}
                raw = r.json()
                self.logger.info("[image_analysis] ollama raw keys=%s response_len=%s",
                                 list(raw.keys()),
                                 len(str(raw.get("response", ""))))
                desc = raw.get("response", "").strip()'''
if old_parse in src:
    src = src.replace(old_parse, new_parse, 1)

# Log input size before sending
old_send = '''        b64 = base64.b64encode(data).decode("ascii")
        url = os.getenv("OLLAMA_URL", "http://localhost:11434")'''
new_send = '''        b64 = base64.b64encode(data).decode("ascii")
        self.logger.info("[image_analysis] sending %d bytes (b64=%d) to ollama",
                         len(data), len(b64))
        url = os.getenv("OLLAMA_URL", "http://localhost:11434")'''
if old_send in src:
    src = src.replace(old_send, new_send, 1)

p.write_text(src, encoding="utf-8")
print("Patched: simplified prompt + logging of input size + raw response keys")