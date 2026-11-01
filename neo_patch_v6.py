"""
neo_patch_v6.py — fixes translate auto-source + language detect short-text
+ hybrid_merger model list + verbose hybrid errors.
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


# =====================================================================
# 1. translate_skill — resolve "auto" source via local detection
# =====================================================================
def t_translate(src):
    if "_detect_source" in src:
        return None, "already patched"

    # Insert helper method into class
    helper = (
        "\n"
        "    def _detect_source(self, text):\n"
        "        \"\"\"Resolve 'auto' to a 2-letter ISO code. MyMemory rejects\n"
        "        'auto' but accepts real codes.\"\"\"\n"
        "        try:\n"
        "            from langdetect import detect as _ld\n"
        "            lang = _ld(text)\n"
        "            if lang and 2 <= len(lang) <= 5:\n"
        "                return lang\n"
        "        except Exception:\n"
        "            pass\n"
        "        t = text.lower()\n"
        "        if any(w in t for w in (\"bonjour\", \"merci\", \"avec \", \"pour \")):\n"
        "            return \"fr\"\n"
        "        if any(w in t for w in (\"hola\", \"gracias\", \"como \", \"pero \")):\n"
        "            return \"es\"\n"
        "        if any(w in t for w in (\"hallo\", \"danke\", \"und \", \"nicht \")):\n"
        "            return \"de\"\n"
        "        if any(w in t for w in (\"habari\", \"asante\", \"jambo\")):\n"
        "            return \"sw\"\n"
        "        return \"en\"\n"
    )

    # Insert helper right before the first method definition after _normalize_lang
    # Find "_normalize_lang" method's closing, then inject
    m = re.search(
        r"(    def _normalize_lang\(self, code\):\n"
        r"        if not code:\n"
        r"            return \"auto\"\n"
        r"        c = str\(code\)\.lower\(\)\.strip\(\)\n"
        r"        return self\._LANG_ALIASES\.get\(c, c\)\n)",
        src,
    )
    if not m:
        return None, "_normalize_lang not found"

    src = src[:m.end()] + helper + src[m.end():]

    # Now inject auto-resolution into process()
    # Find `if src == tgt:` inside process() and prepend the resolver
    anchor = '        if src == tgt:\n            return {"translated": text, "src": src, "tgt": tgt, "method": "identity"}'
    if anchor not in src:
        return None, "src==tgt anchor not found"

    inject = (
        '        # FIXED: resolve "auto" to a real ISO code before sending to MyMemory\n'
        '        if src in ("auto", "autodetect", ""):\n'
        '            src = self._detect_source(text)\n'
        '            logger.info(f"TranslateSkill: resolved auto → {src}")\n'
        '\n'
        + anchor
    )

    src = src.replace(anchor, inject, 1)
    return src, "added _detect_source + auto resolution"


patch("skills/translate_skill.py", t_translate, "translate_skill.py: auto source")


# =====================================================================
# 2. language_detect_skill — mode-vote langdetect for short text
# =====================================================================
def t_langdetect(src):
    # Replace the process() body with a better algorithm
    new_process = (
        "    def process(self, inputs: dict) -> dict:\n"
        "        text = str(inputs.get(\"text\", \"\")).strip()\n"
        "        if not text:\n"
        "            return {\"error\": \"text is required\"}\n"
        "\n"
        "        # 1. Script check — deterministic for non-Latin\n"
        "        for lang, pat in _SCRIPT_RANGES:\n"
        "            if re.search(pat, text):\n"
        "                return {\"detected_language\": lang, \"method\": \"script\"}\n"
        "\n"
        "        # 2. Short Latin text — language-specific keyword hints\n"
        "        t = text.lower()\n"
        "        _HINTS = [\n"
        "            (\"fr\", (\"bonjour\", \"merci\", \"le \", \"la \", \"avec \", \"pour \", \"oui\")),\n"
        "            (\"es\", (\"hola\", \"gracias\", \"el \", \"los \", \"como \", \"pero \", \"mundo\")),\n"
        "            (\"de\", (\"hallo\", \"danke\", \"der \", \"die \", \"das \", \"und \", \"nicht\")),\n"
        "            (\"it\", (\"ciao\", \"grazie\", \"il \", \"la \", \"con \", \"per \")),\n"
        "            (\"pt\", (\"olá\", \"obrigado\", \"com \", \"para \", \"não \")),\n"
        "            (\"sw\", (\"habari\", \"asante\", \"jambo\", \"kwa \")),\n"
        "        ]\n"
        "        if len(text) < 40:\n"
        "            for lang, hints in _HINTS:\n"
        "                if any(h in t for h in hints):\n"
        "                    return {\"detected_language\": lang, \"method\": \"keyword_hint\"}\n"
        "\n"
        "        # 3. Long Latin text — langdetect with mode voting\n"
        "        if _HAS_LANGDETECT and len(text) >= 20:\n"
        "            try:\n"
        "                from collections import Counter\n"
        "                votes = []\n"
        "                for _ in range(5):\n"
        "                    try:\n"
        "                        votes.append(_ld_detect(text))\n"
        "                    except Exception:\n"
        "                        pass\n"
        "                if votes:\n"
        "                    mode = Counter(votes).most_common(1)[0][0]\n"
        "                    if mode:\n"
        "                        return {\"detected_language\": mode, \"method\": \"langdetect_vote\"}\n"
        "            except Exception:\n"
        "                pass\n"
        "\n"
        "        # 4. LLM fallback (short text only)\n"
        "        if len(text) < 40:\n"
        "            llm_result = self._llm(text)\n"
        "            if llm_result:\n"
        "                return {\"detected_language\": llm_result, \"method\": \"llm\"}\n"
        "\n"
        "        return {\"detected_language\": \"en\", \"method\": \"default\"}\n"
    )

    # Find old process() and replace
    m = re.search(
        r"    def process\(self, inputs: dict\) -> dict:[\s\S]*?(?=\n\nclass |\n\ndef |\Z)",
        src,
    )
    if not m:
        return None, "process() not found"

    new_src = src[:m.start()] + new_process + src[m.end():]
    return new_src, "replaced process() with hint + vote algorithm"


patch("skills/language_detect_skill.py", t_langdetect, "language_detect_skill.py: process rewrite")


# =====================================================================
# 3. hybrid_merger — replace ALL Groq models with gpt-oss-120b
# =====================================================================
def t_hybrid(src):
    changes = []
    # Any Groq model that isn't openai/gpt-oss-120b → openai/gpt-oss-120b
    groq_pattern = re.compile(
        r'("provider":\s*"groq"[^}]*?"model":\s*")([^"]+)(")',
        re.DOTALL,
    )
    def _repl(m):
        if m.group(2) != "openai/gpt-oss-120b":
            changes.append(f"{m.group(2)} → gpt-oss-120b")
            return m.group(1) + "openai/gpt-oss-120b" + m.group(3)
        return m.group(0)
    src = groq_pattern.sub(_repl, src)

    if not changes:
        return None, "no Groq models to replace"
    return src, f"replaced {len(changes)} Groq model(s)"


patch("hybrid_merger.py", t_hybrid, "hybrid_merger.py: Groq IDs")


# =====================================================================
# 4. fundibrain.py — expose show_context / clear_context / list_goals
# =====================================================================
def t_fundibrain(src):
    if "def show_context" in src:
        return None, "already patched"

    # Find end of FundiBrain class (before the get_stats method or last method)
    anchor = "    def get_stats(self):"
    if anchor not in src:
        return None, "get_stats anchor not found"

    methods = (
        "    def show_context(self):\n"
        "        \"\"\"Return conversation history.\"\"\"\n"
        "        return str(self.conversation) if self.conversation else \"(empty)\"\n"
        "\n"
        "    def clear_context(self):\n"
        "        \"\"\"Clear conversation history.\"\"\"\n"
        "        self.conversation = []\n"
        "        return \"Context cleared.\"\n"
        "\n"
        "    def list_goals(self):\n"
        "        \"\"\"Return current goals.\"\"\"\n"
        "        return getattr(self.goal_manager, \"goals\", []) or []\n"
        "\n"
        "    def add_goal(self, task):\n"
        "        \"\"\"Add a goal.\"\"\"\n"
        "        self.goal_manager.add_goal(task)\n"
        "        return f\"Goal added: {task}\"\n"
        "\n"
    )

    new = src.replace(anchor, methods + anchor, 1)
    return new, "added show_context / clear_context / list_goals / add_goal"


patch("fundibrain.py", t_fundibrain, "fundibrain.py: context methods")


# =====================================================================
# Report
# =====================================================================
print()
print("=" * 70)
print("  NEO PATCH v6 — RESULTS")
print("=" * 70)
for label, result in results:
    if result.startswith("OK"):
        mark = "✓"
    elif result.startswith("skip"):
        mark = "·"
    else:
        mark = "✗"
    print(f"  [{mark}] {label}")
    print(f"        {result}")
print("=" * 70)
print()
print("Reboot:  python launcher.py")
print("Or with transcript: Start-Transcript launcher_test.log -Force ; python launcher.py")