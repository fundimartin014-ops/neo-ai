"""
neo_patch_v4.py — comprehensive fix installer.

Uses bracket-scanning for list anchors (no fragile multi-line string
matching). Validates every patched file with ast.parse before writing.
Prints the state of each file so we know exactly what's already applied.
"""
import ast
import re
from pathlib import Path

PROJECT = Path.cwd()
changes = []


# =====================================================================
# 1. launcher.py — remove any inner `import re` (any indent level)
# =====================================================================
def fix_launcher_import_re():
    p = PROJECT / "launcher.py"
    src = p.read_text(encoding="utf-8")

    # Match any line that is only "<whitespace>import re<optional comment>"
    pattern = re.compile(r"(?m)^[ \t]+import re[ \t]*(?:#[^\n]*)?\r?\n")
    new, n = pattern.subn("", src)

    if n == 0:
        # Look for the string anywhere inside def main to diagnose
        idx = src.find("def main(")
        if idx != -1 and "import re" in src[idx:]:
            return "FAIL: 'import re' inside main but didn't match pattern (unusual whitespace?)"
        return "skip (no bare 'import re' at any indent)"

    ast.parse(new)
    p.write_text(new, encoding="utf-8")
    return f"removed {n} inner import re line(s)"


changes.append(("launcher.py: inner import re", fix_launcher_import_re()))


# =====================================================================
# 2. video_plugin.py — ensure `def generate(self` exists
# =====================================================================
def fix_video_plugin():
    p = PROJECT / "core" / "plugins" / "video_plugin.py"
    if not p.exists():
        return "FAIL: file not found"
    src = p.read_text(encoding="utf-8")

    if re.search(r"^\s+def generate\(self", src, re.MULTILINE):
        return "skip (already has generate())"
    if "def generate_video" not in src:
        return "FAIL: neither generate nor generate_video found"

    anchor = "    def run(self):"
    if anchor not in src:
        return "FAIL: anchor 'def run' not found"

    shim = (
        "    def generate(self, prompt, width=1024, height=576, seconds=4,\n"
        "                 model_hint=None, seed=None, **kwargs):\n"
        "        \"\"\"Alias for generate_video() — launcher calls .generate().\"\"\"\n"
        "        return self.generate_video(\n"
        "            prompt=prompt, seconds=seconds, width=width,\n"
        "            height=height, seed=seed, model_hint=model_hint,\n"
        "        )\n\n"
    )
    new_src = src.replace(anchor, shim + anchor, 1)
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return "added generate() shim"


changes.append(("video_plugin.py: generate shim", fix_video_plugin()))


# =====================================================================
# 3. launcher.py — extend _COMPUTE_VETOES (bracket-scanner)
# =====================================================================
def fix_compute_vetoes():
    p = PROJECT / "launcher.py"
    src = p.read_text(encoding="utf-8")

    if "block Tavily for self-referential" in src:
        return "skip (already extended)"

    marker = "_COMPUTE_VETOES = ["
    idx = src.find(marker)
    if idx == -1:
        return "FAIL: '_COMPUTE_VETOES = [' marker not found"

    # Scan for matching ]
    open_pos = idx + len(marker) - 1  # position of '['
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
        return "FAIL: matching ']' not found"

    # Trim trailing whitespace/newlines before the ]
    trimmed = src[:close_idx].rstrip()

    extra = (
        '\n'
        '        # ADDED: block Tavily for self-referential + command queries\n'
        '        r"^\\s*who\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+are\\s+you\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+is\\s+your\\s+name\\s*\\??\\s*$",\n'
        '        r"^\\s*what\\s+can\\s+you\\s+do\\s*\\??\\s*$",\n'
        '        r"^\\s*tell\\s+me\\s+about\\s+yourself",\n'
        '        r"^\\s*train\\s+",\n'
        '        r"^\\s*https?://",\n'
        '    '
    )

    new = trimmed + "\n" + extra + src[close_idx:]

    ast.parse(new)
    p.write_text(new, encoding="utf-8")
    return "extended _COMPUTE_VETOES with 7 new patterns"


changes.append(("launcher.py: _COMPUTE_VETOES", fix_compute_vetoes()))


# =====================================================================
# 4. neo_nosignups.py — threshold (handle 5.0/6.0/7.0 variants)
# =====================================================================
def fix_neotool_threshold():
    p = PROJECT / "neo_nosignups.py"
    src = p.read_text(encoding="utf-8")

    # Find any "match_score" line with a numeric threshold
    m = re.search(
        r'(if\s+top_tool\.get\("match_score",\s*0\)\s*<\s*)([0-9.]+)',
        src,
    )
    if not m:
        return "FAIL: couldn't locate match_score threshold"

    current = float(m.group(2))
    if current <= 5.0:
        return f"skip (already ≤5.0, found {current})"

    new_src = src[:m.start(2)] + "5.0" + src[m.end(2):]
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return f"threshold {current} → 5.0"


changes.append(("neo_nosignups.py: threshold", fix_neotool_threshold()))


# =====================================================================
# 5. language_detect_skill.py — threshold (various forms)
# =====================================================================
def fix_lang_detect():
    p = PROJECT / "skills" / "language_detect_skill.py"
    if not p.exists():
        return "FAIL: file not found"
    src = p.read_text(encoding="utf-8")

    # Look for any "len(text) >= N" where N > 10
    m = re.search(r"len\(text\)\s*>=\s*(\d+)", src)
    if not m:
        return "FAIL: couldn't locate 'len(text) >= N'"

    current = int(m.group(1))
    if current <= 10:
        return f"skip (already ≤10, found {current})"

    new_src = src[:m.start(1)] + "10" + src[m.end(1):]
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return f"threshold {current} → 10"


changes.append(("language_detect_skill.py: threshold", fix_lang_detect()))


# =====================================================================
# 6. hybrid_merger.py — replace stale OpenRouter model IDs
# =====================================================================
def fix_hybrid_merger():
    p = PROJECT / "hybrid_merger.py"
    if not p.exists():
        return "FAIL: file not found"
    src = p.read_text(encoding="utf-8")

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
        "openrouter/free": "google/gemma-4-31b-it:free",
    }

    hits = []
    new_src = src
    for old, new in replacements.items():
        if old in new_src:
            new_src = new_src.replace(old, new)
            hits.append(f"{old} → {new}")

    if not hits:
        return "skip (no known stale IDs found)"

    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return f"replaced {len(hits)} stale model ID(s)"


changes.append(("hybrid_merger.py: model IDs", fix_hybrid_merger()))


# =====================================================================
# 7. neo_brain.py — add URL fast path in NeoBrainWrapper.respond
# =====================================================================
def fix_url_fast_path():
    p = PROJECT / "core" / "services" / "neo_brain.py"
    if not p.exists():
        return "FAIL: file not found"
    src = p.read_text(encoding="utf-8")

    if "URL learning fast path" in src:
        return "skip (already patched)"

    anchor = "        # --- Command passthrough"
    if anchor not in src:
        return "FAIL: 'Command passthrough' anchor not found"

    block = (
        "        # --- URL learning fast path -----------------------------------------\n"
        "        if user_input.strip().startswith((\"http://\", \"https://\")):\n"
        "            try:\n"
        "                result = self.brain.learn_from_url(user_input.strip())\n"
        "                self.conversation_history.append({\n"
        "                    \"role\": \"assistant\",\n"
        "                    \"content\": str(result),\n"
        "                    \"mode\": \"URL_LEARN\",\n"
        "                    \"personality\": \"professional\",\n"
        "                })\n"
        "                return self._format_response(\n"
        "                    str(result),\n"
        "                    {\"mode\": \"URL_LEARN\", \"personality\": \"professional\"},\n"
        "                )\n"
        "            except Exception as e:\n"
        "                print(f\"[NeoBrain] URL learn failed: {e}\")\n"
        "        # --- end URL fast path ----------------------------------------------\n\n"
    )

    new_src = src.replace(anchor, block + anchor, 1)
    ast.parse(new_src)
    p.write_text(new_src, encoding="utf-8")
    return "added URL fast path"


changes.append(("neo_brain.py: URL fast path", fix_url_fast_path()))


# =====================================================================
# 8. translate_skill.py — verify aliases present (report only)
# =====================================================================
def verify_translate_aliases():
    p = PROJECT / "skills" / "translate_skill.py"
    if not p.exists():
        return "FAIL: file not found"
    src = p.read_text(encoding="utf-8")
    if "_LANG_ALIASES" in src and "_normalize_lang" in src:
        return "OK (already has aliases + normalizer)"
    return "MISSING (aliases or normalizer not found)"


changes.append(("translate_skill.py: aliases check", verify_translate_aliases()))


# =====================================================================
# Report
# =====================================================================
print()
print("=" * 66)
print("  NEO PATCH v4 — RESULTS")
print("=" * 66)
for label, result in changes:
    if result.startswith("FAIL"):
        marker = "XX"
    elif result.startswith("skip") or result.startswith("OK"):
        marker = "--"
    else:
        marker = "OK"
    print(f"  [{marker}] {label}")
    print(f"        {result}")
print("=" * 66)
print()

# =====================================================================
# Diagnostics — dump current state of key files
# =====================================================================
print("DIAGNOSTICS — current state on disk")
print("-" * 66)

def show(path, pattern, label):
    p = PROJECT / path
    if not p.exists():
        print(f"  {label}: FILE MISSING")
        return
    src = p.read_text(encoding="utf-8")
    matches = re.findall(pattern, src, re.MULTILINE)
    if matches:
        for m in matches[:5]:
            print(f"  {label}: {m if isinstance(m, str) else m}")
    else:
        print(f"  {label}: (not found)")

show("launcher.py", r'.*_COMPUTE_VETOES\s*=\s*\[', "launcher._COMPUTE_VETOES")
show("launcher.py", r'^\s+import re\s*$', "launcher.inner_import_re")
show("neo_nosignups.py", r'if.*match_score.*<\s*([0-9.]+)', "neon.nosig.threshold")
show("skills/language_detect_skill.py", r'len\(text\)\s*>=\s*(\d+)', "langdetect.threshold")
show("hybrid_merger.py", r'"model":\s*"([^"]+:free)"', "hybrid.model_ids")
show("core/services/neo_brain.py", r'.*URL learning fast path', "neobrain.url_fast_path")
show("core/plugins/video_plugin.py", r'^\s+def generate\(self', "video.generate")

print("-" * 66)
print()
print("Next step: python launcher.py > launcher_full.log 2>&1")