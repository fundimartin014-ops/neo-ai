"""
inspect_project.py — Print a full map of the AI project.

Usage:
    python inspect_project.py                # summary by folder
    python inspect_project.py --imports      # also show top imports of each .py
    python inspect_project.py --out tree.txt # write to a file

Safe: read-only. Never executes or modifies project files.
"""

import os
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

# Directories to skip — noisy / not source
SKIP_DIRS = {
    ".venv", "venv", "env", "__pycache__", ".git", ".idea", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".egg-info", "site-packages", ".ipynb_checkpoints",
}

# Extensions worth reporting
KEEP_EXTS = {
    ".py", ".pyi", ".html", ".htm", ".css", ".js", ".json", ".txt",
    ".md", ".yml", ".yaml", ".toml", ".env", ".cfg", ".ini", ".ps1",
    ".sh", ".bat", ".sqlite", ".db",
}

# Files worth showing but treated as binary/opaque
BINARY_EXTS = {".sqlite", ".db", ".pyc", ".pyo", ".png", ".jpg", ".jpeg",
               ".gif", ".webp", ".mp3", ".wav", ".mp4", ".zip", ".tar",
               ".gz", ".whl", ".pt", ".bin", ".onnx", ".faiss", ".index"}


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def count_lines(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return -1


def top_imports(path: Path, limit: int = 8) -> list:
    """Return the first N import lines from a .py file."""
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(200):  # scan at most first 200 lines
                line = f.readline()
                if not line:
                    break
                s = line.strip()
                if s.startswith("import ") or s.startswith("from "):
                    out.append(s)
                    if len(out) >= limit:
                        break
    except Exception:
        pass
    return out


def walk(root: Path):
    """Yield (folder_relpath, [ (file, size, lines) ... ]) grouped by folder."""
    buckets = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # prune skip dirs in place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = "(root)"

        files = []
        for fn in sorted(filenames):
            ext = Path(fn).suffix.lower()
            # .env has no suffix or is '.env' handled below
            if fn == ".env" or fn.endswith(".env"):
                ext = ".env"
            if ext not in KEEP_EXTS and ext not in BINARY_EXTS:
                continue
            p = Path(dirpath) / fn
            try:
                size = p.stat().st_size
            except Exception:
                size = -1
            lines = -1 if ext in BINARY_EXTS else count_lines(p)
            files.append((fn, size, lines, ext))

        if files:
            buckets[rel_dir] = files
    return buckets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imports", action="store_true",
                    help="also list top imports of each .py file")
    ap.add_argument("--out", type=str, default=None,
                    help="write output to a file instead of stdout")
    ap.add_argument("--root", type=str, default=str(ROOT),
                    help="project root (default: script folder)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    buckets = walk(root)

    out_lines = []
    def emit(s=""):
        out_lines.append(s)

    emit("=" * 78)
    emit(f"PROJECT MAP — {root}")
    emit("=" * 78)
    emit()

    total_files = 0
    total_lines = 0
    total_bytes = 0

    for folder in sorted(buckets.keys()):
        emit(f"📁 {folder}/")
        for fn, size, lines, ext in buckets[folder]:
            total_files += 1
            if lines >= 0:
                total_lines += lines
            total_bytes += max(size, 0)
            line_str = f"{lines:>6} lines" if lines >= 0 else "   bin  "
            emit(f"   {line_str}   {human_size(size):>9}   {fn}")
            if args.imports and ext == ".py":
                imports = top_imports(Path(root) / folder.replace("(root)", "") / fn
                                      if folder != "(root)" else Path(root) / fn)
                for imp in imports:
                    emit(f"            → {imp}")
        emit()

    emit("=" * 78)
    emit(f"TOTAL: {total_files} files  |  {total_lines} lines  |  {human_size(total_bytes)}")
    emit("=" * 78)

    text = "\n".join(out_lines)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[inspect_project] Wrote {len(text)} bytes to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()