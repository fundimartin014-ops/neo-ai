#!/usr/bin/env python3
"""scan_ai.py — audit the whole AI project for duplicates and stale files.

Run from project root:  python scan_ai.py
Writes:                 scan_ai_report.txt
"""
from __future__ import annotations

import ast
import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(".").resolve()
REPORT = ROOT / "scan_ai_report.txt"

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".idea", ".vscode", ".ipynb_checkpoints",
    "data", "sandbox", "logs", "temp", "generated_images",
    "models", "vector_store", ".next", "dist", "build",
    "site-packages", ".cache", ".mypy",
}

PATCH_PATTERNS = [
    ("patch_*",        re.compile(r"^patch_.+\.py$", re.I)),
    ("fix_*",          re.compile(r"^fix_.+\.py$", re.I)),
    ("make_*",         re.compile(r"^make_.+\.py$", re.I)),
    ("repair_*",       re.compile(r"^repair_.+\.py$", re.I)),
    ("*.bak",          re.compile(r".+\.bak(\.\d+)?$", re.I)),
    ("*.pre-fix",      re.compile(r".+\.pre-fix.*$", re.I)),
    ("*.save",         re.compile(r".+\.save.*$", re.I)),
    ("*.orig",         re.compile(r".+\.orig.*$", re.I)),
    ("numbered copy",  re.compile(r".+ \(\d+\)\.py$")),
    ("tilde backup",   re.compile(r".+~\d*$")),
]


def walk():
    for dirpath, dirnames, filenames in os.walk(ROOT, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_file():
                yield p


def file_category(p: Path) -> str:
    rel = p.relative_to(ROOT)
    parts = rel.parts
    if len(parts) < 2:
        return "root"
    top = parts[0]
    if top == "core" and len(parts) >= 3 and parts[1] == "plugins":
        return "core/plugins"
    if top in {"skills", "agents", "core", "knowledge", "reasoning", "neofarm",
               "tests", "_archive", "_tools", "config", "docs", "templates",
               "voice", "backened", "frontend", "free-llm-gateway"}:
        return top
    return f"other/{top}"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def top_level_symbols(p: Path):
    try:
        src = p.read_text(encoding="utf-8-sig", errors="ignore")
        tree = ast.parse(src)
    except Exception:
        return set(), set()
    classes, funcs = set(), set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.add(node.name)
    return classes, funcs


def looks_like_patch(name: str):
    for label, pat in PATCH_PATTERNS:
        if pat.match(name):
            return label
    return None


def newest(paths):
    try:
        return max(paths, key=lambda p: p.stat().st_mtime)
    except Exception:
        return paths[0]


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def main():
    all_files = list(walk())
    py_files  = [f for f in all_files if f.suffix == ".py"]
    other     = [f for f in all_files if f.suffix != ".py"]

    by_cat = defaultdict(list)
    for f in py_files:
        by_cat[file_category(f)].append(f)

    hashes = defaultdict(list)
    for f in py_files:
        try:
            hashes[sha256(f)].append(f)
        except Exception:
            pass
    content_dupes = {h: ps for h, ps in hashes.items() if len(ps) > 1}

    by_name = defaultdict(list)
    for f in py_files:
        by_name[f.name].append(f)
    name_collisions = {n: ps for n, ps in by_name.items() if len(ps) > 1}

    patches = []
    for f in all_files:
        label = looks_like_patch(f.name)
        if label:
            patches.append((label, f))

    tiny = [f for f in py_files if f.stat().st_size < 50]

    class_locations = defaultdict(list)
    for f in py_files:
        classes, _ = top_level_symbols(f)
        for c in classes:
            class_locations[c].append(f)
    overlapping_classes = {c: ps for c, ps in class_locations.items() if len(ps) > 1}

    imported = set()
    for pyc in ROOT.rglob("__pycache__/*.pyc"):
        stem = pyc.name.split(".", 1)[0]
        parent = pyc.parent.parent
        try:
            rel_parent = parent.relative_to(ROOT)
        except ValueError:
            continue
        imported.add(f"{str(rel_parent).replace(chr(92), '/')}/{stem}.py")

    # ---------------------------------------------------------------- report
    out = []
    out.append("=" * 78)
    out.append("AI PROJECT SCAN")
    out.append(f"Root:   {ROOT}")
    out.append(f"Ran at: {datetime.now().isoformat(timespec='seconds')}")
    out.append(f"Files:  {len(all_files)} total ({len(py_files)} .py)")
    out.append("=" * 78)

    # 1) files by category (compact: names only)
    out.append("\n## Files by category\n")
    for cat in sorted(by_cat, key=lambda c: (-len(by_cat[c]), c)):
        files = sorted(by_cat[cat], key=lambda p: p.name)
        out.append(f"{cat:22s}  {len(files):4d} files")
        names = [f.name for f in files]
        for i in range(0, len(names), 5):
            chunk = names[i:i+5]
            out.append("    " + "  ".join(f"{n:<38s}" for n in chunk))

    # 2) patches / stale
    out.append("\n## Patch / stale candidates\n")
    if not patches:
        out.append("  (none)")
    else:
        seen = set()
        for label, f in sorted(patches, key=lambda x: str(x[1])):
            rel = _rel(f)
            if rel in seen:
                continue
            seen.add(rel)
            out.append(f"  [{label:14s}]  {rel}")

    # 3) exact content duplicates
    out.append("\n## Duplicate by exact content (sha256)\n")
    if not content_dupes:
        out.append("  (none)")
    else:
        for i, (h, paths) in enumerate(sorted(content_dupes.items(), key=lambda kv: -len(kv[1])), 1):
            try:
                size = paths[0].stat().st_size
            except Exception:
                size = -1
            keep = newest(paths)
            out.append(f"\n  #{i}  ({len(paths)} copies, {size} bytes, sha={h[:10]})")
            out.append(f"       newest: {_rel(keep)}")
            for p in sorted(paths, key=str):
                tag = "  <-- newest" if p == keep else ""
                out.append(f"        {_rel(p)}{tag}")

    # 4) same filename in different dirs
    out.append("\n## Same filename in multiple directories\n")
    if not name_collisions:
        out.append("  (none)")
    else:
        for name in sorted(name_collisions, key=lambda n: (-len(name_collisions[n]), n)):
            paths = sorted(name_collisions[name], key=str)
            keep = newest(paths)
            out.append(f"\n  {name}   ({len(paths)} copies)")
            out.append(f"       newest: {_rel(keep)}")
            for p in paths:
                tag = "  <-- newest" if p == keep else ""
                out.append(f"        {_rel(p)}{tag}")

    # 5) same class name across files
    out.append("\n## Same class name in multiple files (likely overlap)\n")
    shown = 0
    for cname in sorted(overlapping_classes):
        paths = overlapping_classes[cname]
        if not (2 <= len(paths) <= 8):
            continue
        dirs = {p.parent for p in paths}
        if len(dirs) < 2:
            continue
        out.append(f"\n  class {cname}")
        for p in sorted(paths, key=str):
            out.append(f"        {_rel(p)}")
        shown += 1
        if shown >= 60:
            out.append("  ... (truncated at 60)")
            break
    if shown == 0:
        out.append("  (none)")

    # 6) tiny files
    out.append("\n## Empty or near-empty .py files (<50 bytes)\n")
    if not tiny:
        out.append("  (none)")
    else:
        for f in sorted(tiny, key=str):
            out.append(f"  {f.stat().st_size:4d}  {_rel(f)}")

    # 7) non-py suffixes
    out.append("\n## Non-.py files\n")
    if not other:
        out.append("  (none)")
    else:
        by_suffix = defaultdict(int)
        for f in other:
            by_suffix[f.suffix or "(no ext)"] += 1
        for s in sorted(by_suffix, key=lambda s: -by_suffix[s]):
            out.append(f"  {s:14s}  {by_suffix[s]}")

    # 8) files with __pycache__ (i.e. actually imported at least once)
    out.append("\n## Files confirmed imported (have __pycache__)\n")
    if not imported:
        out.append("  (none)")
    else:
        for imp in sorted(imported):
            out.append(f"  {imp}")

    text = "\n".join(out)
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n--- written to {REPORT} ---")


if __name__ == "__main__":
    main()
