"""
neo_patch_v5.py — fixes for the remaining runtime bugs.
Uses regex/robust anchors, validates each file with ast.parse before writing.
Reports what was applied vs already present vs failed.
"""
import ast
import re
from pathlib import Path

PROJECT = Path.cwd()
results = []


def patch(path, transform, label):
    p = PROJECT / path
    if not p.exists():
        results.append((label, "FAIL: file missing"))
        return
    src = p.read_text(encoding="utf-8")
    try:
        new, msg = transform(src)
    except Exception as e:
        results.append((label, f"FAIL: {e}"))
        return
    if new is None:
        results.append((label, f"skip ({msg})"))
        return
    try:
        ast.parse(new)
    except SyntaxError as e:
        results.append((label, f"FAIL syntax: {e}"))
        return
    p.write_text(new, encoding="utf-8")
    results.append((label, f"OK ({msg})"))


# ─────────────────────────────────────────────────────────────────────
# 1. trainer_plugin.py — pass topic via meta={}
# ─────────────────────────────────────────────────────────────────────
def t_trainer(src):
    # find `remember(...topic=detect_topic(text))` and rewrite to meta
    m = re.search(
        r"remember\(\s*text\s*,\s*text\s*,\s*source\s*=\s*\"manual\"\s*,\s*topic\s*=\s*(detect_topic\(text\))\s*\)",
        src,
    )
    if not m:
        if 'meta={"topic"' in src:
            return None, "already patched"
        return None, "pattern not found"
    new = src[:m.start()] + f'remember(text, text, source="manual", meta={{"topic": {m.group(1)}}})' + src[m.end():]
    return new, "topic= → meta={topic:...}"


patch("core/plugins/trainer_plugin.py", t_trainer, "trainer_plugin.py: topic kwarg")


# ─────────────────────────────────────────────────────────────────────
# 2. local_llm.py — fix hardcoded dead OpenRouter default + Groq default
# ─────────────────────────────────────────────────────────────────────
def t_local_llm(src):
    changes = []
    # OpenRouter fallback default
    if '"deepseek/deepseek-r1:free"' in src:
        src = src.replace('"deepseek/deepseek-r1:free"', '"google/gemma-4-31b-it:free"')
        changes.append("OR default → gemma-4-31b")
    # Groq default (llama-3.3-70b-versatile is 404 on Groq now)
    if '"llama-3.3-70b-versatile"' in src:
        src = src.replace('"llama-3.3-70b-versatile"', '"openai/gpt-oss-120b"')
        changes.append("Groq default → gpt-oss-120b")
    if not changes:
        return None, "no stale IDs found"
    return src, ", ".join(changes)


patch("core/local_llm.py", t_local_llm, "local_llm.py: default model IDs")


# ─────────────────────────────────────────────────────────────────────
# 3. translate_skill.py — try MyMemory FIRST (deterministic), LLM second
# ─────────────────────────────────────────────────────────────────────
def t_translate(src):
    # Look for the current ordering in process():
    #   out = self._llm_translate(...)  ... if out: return ... method: "llm"
    #   out = self._mymemory(...)        ... if out: return ... method: "mymemory"
    m = re.search(
        r"(?P<pre>def process\(self, inputs: dict\) -> dict:[\s\S]*?text = str\(inputs\.get\(\"text\", \"\"\)\)\.strip\(\)\n)"
        r"[\s\S]*?"
        r"(?P<tail>\s+return \{\"error\": \"All translation backends failed\"\})",
        src,
    )
    if not m:
        return None, "process() body not matched"

    # Rebuild the middle of process():
    new_body = (
        '\n        src = self._normalize_lang(inputs.get("src", "en"))\n'
        '        tgt = self._normalize_lang(inputs.get("tgt", "es"))\n'
        '        if not text:\n'
        '            return {"error": "text is required"}\n'
        '        if src == tgt:\n'
        '            return {"translated": text, "src": src, "tgt": tgt, "method": "identity"}\n'
        '\n'
        '        logger.info(f"TranslateSkill: {src}->{tgt} \'{text[:60]}\'")\n'
        '\n'
        '        # FIXED: MyMemory first (deterministic), LLM second.\n'
        '        # The LLM was hallucinating wrong languages for short codes\n'
        '        # (e.g. "sw" → Korean) and returning gibberish.\n'
        '        out = self._mymemory(text, src, tgt)\n'
        '        if out:\n'
        '            return {"translated": out, "src": src, "tgt": tgt, "method": "mymemory"}\n'
        '\n'
        '        out = self._llm_translate(text, src, tgt)\n'
        '        if out:\n'
        '            return {"translated": out, "src": src, "tgt": tgt, "method": "llm"}\n'
    )

    head = m.group("pre") + new_body
    tail = m.group("tail")
    new = src[:m.start()] + head + tail + src[m.end():]
    return new, "swapped order: MyMemory first"


patch("skills/translate_skill.py", t_translate, "translate_skill.py: MyMemory first")


# ─────────────────────────────────────────────────────────────────────
# 4. language_detect_skill.py — force threshold to 10
# ─────────────────────────────────────────────────────────────────────
def t_langdetect(src):
    # any "len(text) >= N" form
    m = re.search(r"len\(text\)\s*>=\s*(\d+)", src)
    if not m:
        return None, "no len(text) >= N found"
    current = int(m.group(1))
    if current <= 10:
        return None, f"already ≤10 ({current})"
    new = src[:m.start(1)] + "10" + src[m.end(1):]
    return new, f"threshold {current} → 10"


patch("skills/language_detect_skill.py", t_langdetect, "language_detect_skill.py: threshold")


# ─────────────────────────────────────────────────────────────────────
# 5. neo_nosignups.py — add explicit intent map for short queries
# ─────────────────────────────────────────────────────────────────────
def t_neotool(src):
    if "_EXPLICIT_INTENTS" in src:
        return None, "already patched"

    anchor = "    def handle_intent(self, user_message: str) -> Dict:"
    if anchor not in src:
        return None, "handle_intent anchor not found"

    # Insert explicit intents dict + early check at the top of handle_intent
    injection = (
        '    # ADDED: explicit intent shortcuts for short 2-token queries.\n'
        '    # The score-based matcher can\'t reliably hit these (they\'re\n'
        '    # genuinely short and generic) so hardcode them.\n'
        '    _EXPLICIT_INTENTS = {\n'
        '        "test regex": "regexr",\n'
        '        "regex test": "regexr",\n'
        '        "try regex": "regexr",\n'
        '        "compress image": "squoosh",\n'
        '        "compress a picture": "squoosh",\n'
        '        "edit markdown": "stackedit",\n'
        '        "markdown editor": "stackedit",\n'
        '        "visualize json": "json-crack",\n'
        '        "view json": "json-crack",\n'
        '        "edit pdf": "bentopdf",\n'
        '        "merge pdf": "bentopdf",\n'
        '        "convert pdf": "bentopdf",\n'
        '        "draw diagram": "excalidraw",\n'
        '        "draw a diagram": "excalidraw",\n'
        '        "make a diagram": "excalidraw",\n'
        '        "create a diagram": "excalidraw",\n'
        '    }\n\n'
    )

    # Insert right before the `def handle_intent` signature
    new = src.replace(anchor, injection + anchor, 1)

    # Now insert the explicit check just after the text-op veto
    veto_end = "                \"response_text\": None\n            }\n"
    # Find the FIRST occurrence of that block inside handle_intent
    check_code = (
        '        # FIXED: explicit intent shortcuts\n'
        '        _q = (user_message or "").strip().lower()\n'
        '        _explicit = self._EXPLICIT_INTENTS.get(_q)\n'
        '        if _explicit:\n'
        '            _tool = self.registry.get_tool_by_id(_explicit)\n'
        '            if _tool:\n'
        '                _sugg = self.integrator.suggest_tools_for_message(user_message, top_k=1) or [_tool]\n'
        '                _iframe = None\n'
        '                _integ = _sugg[0].get("integration_type", "iframe") if isinstance(_sugg[0], dict) else "iframe"\n'
        '                if _integ in ("iframe", "iframe_or_selfhost"):\n'
        '                    _iframe = self.integrator.get_iframe_embed(_explicit, height="450px")\n'
        '                _resp = f"I found **{_tool[\'name\']}** for that! {_tool[\'description\']}"\n'
        '                if _tool.get("github"):\n'
        '                    _resp += f" You can also [self-host it]({_tool[\'github\']})."\n'
        '                return {\n'
        '                    "has_tool": True,\n'
        '                    "tools": _sugg if isinstance(_sugg, list) else [_tool],\n'
        '                    "iframe_html": _iframe,\n'
        '                    "response_text": _resp,\n'
        '                }\n'
    )

    # Insert after the text-op veto block
    idx = new.find(veto_end)
    if idx == -1:
        return None, "veto block not found for insertion"
    idx += len(veto_end)
    new = new[:idx] + "\n" + check_code + new[idx:]

    return new, "added explicit intent map + early check"


patch("neo_nosignups.py", t_neotool, "neo_nosignups.py: explicit intents")


# ─────────────────────────────────────────────────────────────────────
# 6. hybrid_merger.py — replace any remaining dead model IDs
# ─────────────────────────────────────────────────────────────────────
def t_hybrid(src):
    replacements = {
        "meta-llama/llama-3.3-70b-instruct:free": "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemini-2.5-flash-preview:free": "google/gemma-4-31b-it:free",
        "google/gemini-2.0-flash-exp:free": "google/gemma-4-26b-a4b-it:free",
        "google/gemini-2.0-flash-thinking-exp:free": "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemini-2.0-pro-exp-02-05:free": "qwen/qwen3.8-27b:free",
        "google/gemini-1.5-flash:free": "liquid/lfm-2.5-2.6b:free",
        "openai/gpt-oss-120b:free": "google/gemma-4-26b-a4b-it:free",
        "qwen/qwen3-235b-a22b:free": "qwen/qwen3.8-27b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free": "cohere/north-mini-code:free",
        "deepseek/deepseek-r1:free": "nvidia/nemotron-3-super-120b-a12b:free",
        "deepseek/deepseek-chat:free": "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free": "nvidia/nemotron-3-super-120b-a12b:free",
    }
    hits = []
    for old, new in replacements.items():
        if old in src:
            src = src.replace(old, new)
            hits.append(old)
    if not hits:
        return None, "no known stale IDs found"
    return src, f"replaced {len(hits)} IDs"


patch("hybrid_merger.py", t_hybrid, "hybrid_merger.py: model IDs")


# ─────────────────────────────────────────────────────────────────────
# 7. launcher.py — _COMPUTE_VETOES extension (bracket-scanner)
# ─────────────────────────────────────────────────────────────────────
def t_vetoes(src):
    if "block Tavily for self-referential" in src:
        return None, "already extended"
    marker = "_COMPUTE_VETOES = ["
    idx = src.find(marker)
    if idx == -1:
        return None, "marker not found"
    open_pos = idx + len(marker) - 1
    depth = 0
    close_idx = None
    for i in range(open_pos, len(src)):
        ch = src[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                close_idx = i
                break
    if close_idx is None:
        return None, "closing bracket not found"
    trimmed = src[:close_idx].rstrip()
    extra = (
        '\n        # ADDED: block Tavily for self-referential + command queries\n'
        '        r"^\\s*who\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+is\\s+your\\s+name\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+can\\s+you\\s+do\\s*\\??\\s*$",\n'
        '        r"^\\s*tell\\s+me\\s+about\\s+yourself",\n'
        '        r"^\\s*train\\s+",\n'
        '        r"^\\s*https?://",\n    '
    )
    new = trimmed + extra + src[close_idx:]
    return new, "extended with 7 patterns"


patch("launcher.py", t_vetoes, "launcher.py: _COMPUTE_VETOES")


# ─────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────
print()
print("=" * 68)
print("  NEO PATCH v5 — RESULTS")
print("=" * 68)
for label, result in results:
    if result.startswith("OK"):
        mark = "✓"
    elif result.startswith("skip"):
        mark = "·"
    else:
        mark = "✗"
    print(f"  [{mark}] {label}")
    print(f"        {result}")
print("=" * 68)
print()


# ─────────────────────────────────────────────────────────────────────
# Diagnostics — verify current disk state
# ─────────────────────────────────────────────────────────────────────
print("DIAGNOSTICS")
print("-" * 68)


def diag(path, pattern, label):
    p = PROJECT / path
    if not p.exists():
        print(f"  {label}: FILE MISSING")
        return
    src = p.read_text(encoding="utf-8")
    ms = re.findall(pattern, src, re.MULTILINE)
    if not ms:
        print(f"  {label}: (not found)")
    else:
        for m in ms[:4]:
            print(f"  {label}: {m}")


diag("core/local_llm.py", r'"([^"]*(?:free|gpt-oss|gemma)[^"]*)"', "local_llm.defaults")
diag("skills/translate_skill.py", r'(_mymemory|_llm_translate)\(', "translate.order")
diag("skills/language_detect_skill.py", r'len\(text\)\s*>=\s*(\d+)', "langdetect.threshold")
diag("neo_nosignups.py", r"_EXPLICIT_INTENTS", "neotool.explicit_map")
diag("core/plugins/trainer_plugin.py", r'remember\([^)]*\)', "trainer.remember_call")
diag("hybrid_merger.py", r'"model":\s*"([^"]+)"', "hybrid.models")
diag("launcher.py", r'block Tavily|_COMPUTE_VETOES', "launcher.vetoes")

print("-" * 68)
print()
print("Reboot: python launcher.py")
print("Or capture: Start-Transcript launcher_full.log -Force ; python launcher.py")