from pathlib import Path

for fname in ("launcher.py", "core/orchestrator.py", "core/local_llm.py",
              "core/llm_router.py", "fundibrain.py"):
    p = Path(fname)
    if not p.exists():
        continue
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

    # Does the file use `re.` anywhere?
    uses_re = any("re." in l and not l.strip().startswith("#") for l in lines)
    # Does it already import re?
    has_import = any(l.strip() == "import re" for l in lines)

    if uses_re and not has_import:
        # Insert "import re" right after the first existing import or docstring end
        insert_at = 0
        in_doc = False
        for i, l in enumerate(lines):
            s = l.strip()
            if i == 0 and s.startswith(('"""', "'''")):
                in_doc = True
                continue
            if in_doc:
                if s.endswith(('"""', "'''")):
                    in_doc = False
                    insert_at = i + 1
                continue
            if s.startswith(("import ", "from ")):
                insert_at = i
                break
        lines.insert(insert_at, "import re\n")
        p.write_text("".join(lines), encoding="utf-8")
        print(f"  + added import re to {fname}")
    else:
        state = "already imports re" if has_import else ("does not use re" if not uses_re else "?")
        print(f"  - {fname}: {state}")