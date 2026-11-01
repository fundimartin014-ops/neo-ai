"""
trace_usage.py — runtime usage tracer for the Neo project.

Hooks builtins.__import__, boots launcher.py, and on exit writes a report:
  - every project .py file that was actually imported (in load order)
  - every project .py file that was NEVER imported (the idle set)
  - coverage percentage

Usage (from project root, venv active):

    python trace_usage.py                         # boot + trace, report on Ctrl+C/exit
    python trace_usage.py --web                   # pass --web to launcher
    python trace_usage.py --out used.txt          # custom output path
    python trace_usage.py --no-trace              # report on current sys.modules only
    python trace_usage.py --include-3rdparty      # also list installed third-party modules

Safe: read-only, no side effects on your project files.
"""

import argparse
import atexit
import builtins
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

SKIP_DIRS = {
    ".venv", "venv", "env", "__pycache__", ".git", ".idea", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
    "site-packages", ".ipynb_checkpoints", ".worktrees",
}

_start_time = None
_import_log = []          # [(module_name, absolute_path, t_seconds)]
_original_import = builtins.__import__


def _is_project_file(path: str) -> bool:
    if not path:
        return False
    try:
        p = Path(path).resolve()
        p.relative_to(PROJECT_ROOT)
    except Exception:
        return False
    for part in p.parts:
        if part in SKIP_DIRS:
            return False
    return True


def _path_of(mod_name: str):
    mod = sys.modules.get(mod_name)
    if mod is None:
        return None
    f = getattr(mod, "__file__", None)
    if not f:
        return None
    try:
        return str(Path(f).resolve())
    except Exception:
        return f


def _hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
    result = _original_import(name, globals, locals, fromlist, level)
    if _start_time is None:
        return result
    try:
        path = _path_of(name)
        if path and _is_project_file(path):
            _import_log.append((name, path, time.time() - _start_time))
    except Exception:
        pass
    return result


def _walk_disk_py():
    files = set()
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py"):
                files.add(str((Path(dirpath) / fn).resolve()))
    return files


def _rel(p):
    try:
        return str(Path(p).relative_to(PROJECT_ROOT))
    except Exception:
        return p


def _build_report(out_path: str = None, include_3rdparty: bool = False):
    disk = _walk_disk_py()
    used = {p for _, p, _ in _import_log}
    idle = disk - used

    L = []
    L.append("=" * 78)
    L.append("NEO RUNTIME USAGE REPORT")
    L.append("=" * 78)
    L.append(f"Generated:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"Project root: {PROJECT_ROOT}")
    L.append("")
    L.append(f"Total .py on disk:      {len(disk)}")
    L.append(f"Total .py imported:     {len(used)}")
    L.append(f"Total .py idle:         {len(idle)}")
    L.append(f"Coverage:               {len(used) / max(len(disk), 1) * 100:.1f}%")
    L.append("")

    L.append("-" * 78)
    L.append("IMPORT ORDER (chronological, project files only)")
    L.append("-" * 78)
    for mod, path, ts in _import_log:
        L.append(f"  [{ts:7.3f}s] {mod:<45} → {_rel(path)}")
    L.append("")

    L.append("-" * 78)
    L.append(f"IDLE FILES ({len(idle)}) — present on disk, never imported")
    L.append("-" * 78)
    for path in sorted(idle):
        L.append(f"  {_rel(path)}")
    L.append("")

    if include_3rdparty:
        L.append("-" * 78)
        L.append("THIRD-PARTY MODULES IMPORTED")
        L.append("-" * 78)
        third = []
        for name, mod in list(sys.modules.items()):
            f = getattr(mod, "__file__", None)
            if f and not _is_project_file(f):
                try:
                    Path(f).resolve().relative_to(PROJECT_ROOT)
                except Exception:
                    third.append(name)
        for name in sorted(set(third)):
            L.append(f"  {name}")
        L.append("")

    L.append("=" * 78)

    text = "\n".join(L)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"\n[trace] Report → {out_path}")
    else:
        print("\n" + text)


def _on_exit():
    builtins.__import__ = _original_import
    if _import_log:
        _build_report(out_path=_out_path, include_3rdparty=_include_3rd)


def _no_trace_report(out_path):
    """Report on the current process's already-loaded modules."""
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if f and _is_project_file(f):
            _import_log.append((name, str(Path(f).resolve()), 0.0))
    _build_report(out_path=out_path)


_out_path = "usage_report.txt"
_include_3rd = False


def main():
    global _start_time, _out_path, _include_3rd

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", default="usage_report.txt")
    ap.add_argument("--no-trace", action="store_true")
    ap.add_argument("--include-3rdparty", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    known, unknown = ap.parse_known_args()

    if known.help:
        print(__doc__)
        return

    _out_path = known.out
    _include_3rd = known.include_3rdparty

    if known.no_trace:
        _no_trace_report(_out_path)
        return

    builtins.__import__ = _hooked_import
    _start_time = time.time()
    atexit.register(_on_exit)

    # Forward unknown args (like --web) to launcher
    sys.argv = [sys.argv[0]] + unknown

    import launcher
    launcher.main()   # returns after Ctrl+C / exit


if __name__ == "__main__":
    main()