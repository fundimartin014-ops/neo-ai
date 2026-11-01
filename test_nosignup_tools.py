"""test_nosignup_tools.py — validate every entry in tools.json.

Default: schema-only (fast, offline, no network).
--live:  also HEAD-request each URL to check it responds (5s timeout, threaded).

Usage:
    python test_nosignup_tools.py                # schema check, all 245
    python test_nosignup_tools.py --live         # + URL reachability
    python test_nosignup_tools.py --live --workers 8
    python test_nosignup_tools.py --all          # print every tool (not just fails)
    python test_nosignup_tools.py --category design
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

TOOLS_JSON = Path("tools.json")

REQUIRED_FIELDS = ("id", "name", "description", "url", "category", "tags")
ALLOWED_SECTIONS = {"featured", "editors-pick", "meets-criteria", ""}


def load_tools() -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    data = json.loads(TOOLS_JSON.read_text(encoding="utf-8"))
    declared_cats = [c["id"] for c in data.get("categories", [])]
    return data.get("tools", []), declared_cats, data


def check_schema(tool: Dict[str, Any], declared_cats: List[str]) -> List[str]:
    errs = []
    for f in REQUIRED_FIELDS:
        if f not in tool:
            errs.append(f"missing field: {f}")
    tid = tool.get("id", "")
    if tid and not tid.replace("-", "").replace("_", "").isalnum():
        errs.append(f"id not slug-like: {tid!r}")
    name = tool.get("name", "")
    if not name or len(name) < 2:
        errs.append(f"name too short: {name!r}")
    url = tool.get("url", "")
    if url:
        if not (url.startswith("http://") or url.startswith("https://")):
            errs.append(f"url not http(s): {url!r}")
    if tool.get("category") not in declared_cats:
        errs.append(f"category {tool.get('category')!r} not in declared list")
    if not isinstance(tool.get("tags"), list):
        errs.append("tags not a list")
    section = tool.get("section", "")
    if section not in ALLOWED_SECTIONS:
        errs.append(f"unknown section: {section!r}")
    return errs


_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/125.0.0.0 Safari/537.36")


def head_ok(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Try HEAD then GET. Any HTTP response (even 4xx) counts as reachable;
    only network-level failures count as unreachable. Cloudflare-fronted
    sites often block HEAD, so the GET fallback matters.
    """
    last_err = "unreachable"
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, str(r.status)
        except urllib.error.HTTPError as e:
            # Any HTTP status means the host answered — treat as reachable.
            return True, f"{e.code}"
        except urllib.error.URLError as e:
            last_err = f"URLError:{getattr(e, 'reason', e)}"
        except Exception as e:
            last_err = f"{type(e).__name__}"
    return False, last_err


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="check URLs over the network")
    ap.add_argument("--all", action="store_true", help="print every tool")
    ap.add_argument("--category", type=str, default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=5)
    args = ap.parse_args()

    tools, declared_cats, _ = load_tools()
    if args.category:
        tools = [t for t in tools if t.get("category") == args.category]
    print(f"Loaded {len(tools)} tools from {TOOLS_JSON}")
    print(f"Declared categories: {', '.join(declared_cats)}")
    print()

    # ---- schema pass ----
    schema_fails = []
    seen_ids = {}
    for t in tools:
        tid = t.get("id", "")
        if tid in seen_ids:
            schema_fails.append((tid, ["duplicate id"]))
        seen_ids[tid] = True
        errs = check_schema(t, declared_cats)
        if errs:
            schema_fails.append((tid or "(no-id)", errs))

    # ---- live pass ----
    live_results = {}
    if args.live:
        print(f"Live URL check: {len(tools)} URLs, {args.workers} workers, {args.timeout}s timeout")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fut = {pool.submit(head_ok, t["url"], args.timeout): t["id"]
                   for t in tools if t.get("url")}
            done = 0
            for f in as_completed(fut):
                tid = fut[f]
                try:
                    live_results[tid] = f.result()
                except Exception as e:
                    live_results[tid] = (False, type(e).__name__)
                done += 1
                if done % 25 == 0:
                    print(f"  ... {done}/{len(fut)}")
        print()

    # ---- per-tool report ----
    print(f"{'ID':<40} {'Name':<35} {'Cat':<14} Schema Live")
    print("-" * 110)
    for t in tools:
        tid = t.get("id", "")
        name = (t.get("name", "") or "")[:33]
        cat = t.get("category", "")
        schema_ok = not any(fid == tid for fid, _ in schema_fails)
        live_ok = ""
        if args.live:
            ok, status = live_results.get(tid, (None, ""))
            live_ok = "ok" if ok else "FAIL" if ok is False else "-"
        if args.all or not schema_ok or (args.live and live_ok == "FAIL"):
            s = "\u2705" if schema_ok else "\u274C"
            l = live_ok or "  -"
            print(f"{tid:<40} {name:<35} {cat:<14} {s:<6} {l}")

    # ---- summary ----
    print()
    print("=" * 72)
    print(f"  TOOLS:    {len(tools)}")
    print(f"  Schema:   {len(tools) - len(schema_fails)} OK / {len(schema_fails)} failed")
    if args.live:
        live_ok = sum(1 for ok, _ in live_results.values() if ok)
        live_bad = sum(1 for ok, _ in live_results.values() if ok is False)
        print(f"  Live:     {live_ok} reachable / {live_bad} unreachable")
    print("=" * 72)

    if schema_fails:
        print()
        print("SCHEMA FAILURES:")
        for tid, errs in schema_fails:
            print(f"  - {tid}: {'; '.join(errs)}")
        return 1

    if args.live:
        unreachable = [(tid, st) for tid, (ok, st) in live_results.items() if ok is False]
        if unreachable:
            print()
            print("UNREACHABLE URLs:")
            for tid, st in unreachable:
                print(f"  - {tid}: {st}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
