"""
neo_patch_v3.py — patches for the remaining 8 bugs.
Validates each patched file with ast.parse before writing.
"""
import ast
import re
from pathlib import Path

PROJECT = Path.cwd()
changes = []

# ─────────────────────────────────────────────────────────────────────
# Fix 1 — remove inner `import re` from launcher.py main()
# ─────────────────────────────────────────────────────────────────────
def fix_launcher_import_re():
    p = PROJECT / "launcher.py"
    src = p.read_text(encoding="utf-8")
    lines = src.split("\n")
    out = []
    removed = 0
    for ln in lines:
        # Any INDENTED `import re` inside the file (should only be inside main)
        if re.fullmatch(r"\s+import re\s*", ln):
            removed += 1
            continue
        out.append(ln)
    if removed == 0:
        return "skip (no inner import re found)"
    new = "\n".join(out)
    ast.parse(new)
    p.write_text(new, encoding="utf-8")
    return f"removed {removed} inner import re line(s)"

changes.append(("launcher.py: inner import re", fix_launcher_import_re()))


# ─────────────────────────────────────────────────────────────────────
# Fix 2 — add `generate` shim to video_plugin.py
# ─────────────────────────────────────────────────────────────────────
def fix_video_plugin():
    p = PROJECT / "core" / "plugins" / "video_plugin.py"
    src = p.read_text(encoding="utf-8")
    if "def generate(self" in src:
        return "skip (already has generate)"

    anchor = "    def run(self):"
    if anchor not in src:
        return "FAIL (anchor 'def run' not found)"

    shim = (
        "    def generate(self, prompt, width=1024, height=576, seconds=4,\n"
        "                 model_hint=None, seed=None, **kwargs):\n"
        "        \"\"\"Alias for generate_video() — the launcher calls .generate().\"\"\"\n"
        "        return self.generate_video(\n"
        "            prompt=prompt, seconds=seconds, width=width,\n"
        "            height=height, seed=seed, model_hint=model_hint,\n"
        "        )\n\n"
    )
    new = src.replace(anchor, shim + anchor, 1)
    ast.parse(new)
    p.write_text(new, encoding="utf-8")
    return "added generate() shim"

changes.append(("video_plugin.py: generate shim", fix_video_plugin()))


# ─────────────────────────────────────────────────────────────────────
# Fix 3-5 — extend _COMPUTE_VETOES in launcher.py
# ─────────────────────────────────────────────────────────────────────
def fix_compute_vetoes():
    p = PROJECT / "launcher.py"
    src = p.read_text(encoding="utf-8")

    # Find the _COMPUTE_VETOES list and extend it
    anchor = '        r"^\\s*reverse\\s+a?\\s*string",\n    ]'
    if anchor not in src:
        # fallback: single-quote version
        anchor = "        r\"^\\s*reverse\\s+a?\\s*string\",\n    ]"
    if anchor not in src:
        return "FAIL (couldn't find _COMPUTE_VETOES end)"

    extra = (
        '        r"^\\s*reverse\\s+a?\\s*string",\n'
        '        # ADDED: block Tavily for self-referential + command queries\n'
        '        r"^\\s*who\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+is\\s+your\\s+name\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+can\\s+you\\s+do\\s*\\??\\s*$",\n'
        '        r"^\\s*tell\\s+me\\s+about\\s+yourself",\n'
        '        r"^\\s*train\\s+",\n'
        '        r"^\\s*https?://",\n'
        '    ]'
    )
    new = src.replace(anchor, extra, 1)
    if new == src:
        return "skip (already extended?)"
    ast.parse(new)
    p.write_text(new, encoding="utf-8")
    return "extended _COMPUTE_VETOES with 7 new patterns"

changes.append(("launcher.py: _COMPUTE_VETOES", fix_compute_vetoes()))


# ─────────────────────────────────────────────────────────────────────
# Fix 6 — NeoToolPlugin threshold 6.0 → 5.0
# ─────────────────────────────────────────────────────────────────────
def fix_neotool_threshold():
    p = PROJECT / "neo_nosignups.py"
    src = p.read_text(encoding="utf-8")
    old = 'if top_tool.get("match_score", 0) < 6.0 or top_tool.get("distinct_tokens", 0) < 2:'
    if old not in src:
        old = "if top_tool.get(\"match_score\", 0) < 6.0 or top_tool.get(\"distinct_tokens\", 0) < 2:"
    if old not in src:
        return "skip (6.0 threshold not found)"
    new = old.replace("< 6.0", "< 5.0")
    new_src = src.replace(old, new, 1)
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return "threshold 6.0 → 5.0"

changes.append(("neo_nosignups.py: threshold", fix_neotool_threshold()))


# ─────────────────────────────────────────────────────────────────────
# Fix 7 — language_detect threshold 20 → 10
# ─────────────────────────────────────────────────────────────────────
def fix_lang_detect():
    p = PROJECT / "skills" / "language_detect_skill.py"
    src = p.read_text(encoding="utf-8")
    old = "if _HAS_LANGDETECT and len(text) >= 20:"
    if old not in src:
        return "skip (threshold line not found)"
    new_src = src.replace(old, "if _HAS_LANGDETECT and len(text) >= 10:", 1)
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return "threshold 20 → 10"

changes.append(("language_detect_skill.py: threshold", fix_lang_detect()))


# ─────────────────────────────────────────────────────────────────────
# Fix 8 — translate_skill lang aliases
# ─────────────────────────────────────────────────────────────────────
def fix_translate_aliases():
    p = PROJECT / "skills" / "translate_skill.py"
    src = p.read_text(encoding="utf-8")
    if "_LANG_ALIASES" in src:
        return "skip (already patched)"

    # Insert alias dict + normalizer right after `def __init__(self):` (first occurrence)
    anchor_re = re.compile(r"(class TranslateSkill:[\s\S]*?def __init__\(self\):\n\s*pass\n)")
    m = anchor_re.search(src)
    if not m:
        return "FAIL (anchor not found)"

    alias_block = (
        "\n"
        "    _LANG_ALIASES = {\n"
        '        "swahili": "sw", "kiswahili": "sw",\n'
        '        "english": "en", "spanish": "es", "espanol": "es",\n'
        '        "french": "fr", "german": "de", "italian": "it",\n'
        '        "portuguese": "pt", "russian": "ru", "chinese": "zh",\n'
        '        "japanese": "ja", "korean": "ko", "arabic": "ar",\n'
        '        "hindi": "hi", "somali": "so", "amharic": "am",\n'
        "    }\n"
        "\n"
        "    def _normalize_lang(self, code):\n"
        '        if not code:\n            return "auto"\n'
        "        c = str(code).lower().strip()\n"
        "        return self._LANG_ALIASES.get(c, c)\n"
    )

    new_src = src[:m.end()] + alias_block + src[m.end():]
    # Also patch process() to call normalizer
    old_src_assign = 'src = str(inputs.get("src", "en")).lower()'
    if old_src_assign in new_src:
        new_src = new_src.replace(
            old_src_assign,
            'src = self._normalize_lang(inputs.get("src", "en"))',
            1,
        )
    old_tgt_assign = 'tgt = str(inputs.get("tgt", "es")).lower()'
    if old_tgt_assign in new_src:
        new_src = new_src.replace(
            old_tgt_assign,
            'tgt = self._normalize_lang(inputs.get("tgt", "es"))',
            1,
        )
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return "added lang aliases + normalizer"

changes.append(("translate_skill.py: aliases", fix_translate_aliases()))


# ─────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("  NEO PATCH v3 — RESULTS")
print("=" * 62)
for label, result in changes:
    marker = "OK  " if not result.startswith(("FAIL", "skip")) else ("--  " if result.startswith("skip") else "XX  ")
    print(f"  {marker}{label}")
    print(f"      {result}")
print("=" * 62)
print()
print("Next: python launcher.py > launcher_full.log 2>&1")