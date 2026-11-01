from pathlib import Path
import py_compile

root = Path(".").resolve()

# ============================================================
# 1. Fix the two test bugs in test_new_features.py
# ============================================================
tnf = root / "test_new_features.py"
src = tnf.read_text(encoding="utf-8")

# Bug 1 — area bound too tight (0.01deg x 0.01deg ~ 123 ha at Kenya lat)
old = '    assert ha < 100, f"unreasonable area: {ha} ha"'
new = '    assert 0 < ha < 1000, f"unreasonable area: {ha} ha"'
if old in src:
    src = src.replace(old, new, 1)
    print("[ok] fixed geo area bound (100 -> 1000 ha)")
else:
    print("[warn] geo area bound anchor not found")

# Bug 2 — _collect_jobs is nested inside register_scheduler_routes
old_test = (
    'def test_scheduler_collect_jobs():\n'
    '    import scheduler_ui\n'
    '    jobs, sources = scheduler_ui._collect_jobs()\n'
    '    # may be empty on a clean machine\n'
    '    return f"{len(jobs)} jobs from {len(sources)} source(s)"'
)
new_test = (
    'def test_scheduler_collect_jobs():\n'
    '    try:\n'
    '        from flask import Flask\n'
    '    except ImportError:\n'
    '        return ("skip", "flask not installed")\n'
    '    import scheduler_ui\n'
    '    app = Flask(__name__)\n'
    '    scheduler_ui.register_scheduler_routes(app)\n'
    '    c = app.test_client()\n'
    '    r = c.get("/api/scheduler")\n'
    '    assert r.status_code == 200, f"status {r.status_code}"\n'
    '    body = r.get_json()\n'
    '    assert "jobs" in body and "sources" in body\n'
    '    return f"{len(body[chr(34)+chr(34)])} jobs" if False else \\\n'
    '           f"{len(body[\'jobs\'])} jobs from {len(body[\'sources\'])} source(s)"'
)
if old_test in src:
    src = src.replace(old_test, new_test, 1)
    print("[ok] fixed scheduler.collect_jobs to use Flask test client")
else:
    print("[warn] scheduler test anchor not found")

tnf.write_text(src, encoding="utf-8")

# ============================================================
# 2. test_nosignup_tools.py — per-tool validator
# ============================================================
tool_test = r'''"""test_nosignup_tools.py — validate every entry in tools.json.

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


def head_ok(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """HEAD request; if 405/501, fall back to a short GET."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": "Neo/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, str(r.status)
        except urllib.error.HTTPError as e:
            if e.code in (405, 501) and method == "HEAD":
                continue
            return True, f"{e.code}"      # server responded, just not 200
        except Exception as e:
            return False, f"{type(e).__name__}"
    return False, "unreachable"


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
'''
(root / "test_nosignup_tools.py").write_text(tool_test, encoding="utf-8")
print("[ok] test_nosignup_tools.py")

# ============================================================
# 3. core/reasoning/verification.py — the "reason like me" layer
# ============================================================
(root / "core" / "reasoning").mkdir(parents=True, exist_ok=True)
(root / "core" / "reasoning" / "__init__.py").write_text(
    '"""Reasoning: decompose -> draft -> critique -> revise -> confidence."""\n',
    encoding="utf-8",
)

verif = r'''"""Verification reasoning loop.

This is what I do that Neo did not:

   1. DECOMPOSE   — split a query into sub-questions before answering
   2. DRAFT       — produce a first answer
   3. CRITIQUE    — re-read the draft against the original question and flag:
                    * does it actually answer?
                    * did it invent facts not in the source/context?
                    * did it skip part of the question?
                    * is it honest about uncertainty?
   4. REVISE      — if critique flags issues, regenerate with the critique
                    as explicit feedback
   5. CONFIDENCE  — return {answer, confidence, critique, sub_questions}

Every step is an LLM call. The LLM doesn't need to be smarter than the
underlying model — the structure (verify after generating) is what makes
the output better.

Usage:
    from core.reasoning.verification import VerificationLayer
    from core.local_llm import LocalLLM

    layer = VerificationLayer(LocalLLM())
    out = layer.reason("What is the capital of Burkina Faso?")
    print(out["answer"], out["confidence"])

Enable in Neo by setting NEO_REASONING_MODE=verify in .env.
"""
from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("reasoning.verification")

MAX_STEPS = 5


# --------------------------------------------------------------------------
# LLM adapter — accepts anything with .generate(prompt=...) or .chat([...])
# --------------------------------------------------------------------------
class _Adapter:
    def __init__(self, llm):
        self.llm = llm

    def ask(self, system: str, user: str, max_tokens: int = 1024) -> str:
        # try .generate first (LocalLLM style)
        gen = getattr(self.llm, "generate", None)
        if callable(gen):
            try:
                return str(gen(user, system=system, max_tokens=max_tokens) or "").strip()
            except TypeError:
                try:
                    return str(gen(prompt=user, system_prompt=system,
                                   max_tokens=max_tokens) or "").strip()
                except Exception:
                    pass
            except Exception:
                pass
        # then .chat (OpenAI style)
        chat = getattr(self.llm, "chat", None)
        if callable(chat):
            try:
                out = chat([{"role": "system", "content": system},
                            {"role": "user", "content": user}])
                return str(out or "").strip()
            except Exception:
                pass
        # last resort: make it a coroutine
        try:
            import asyncio
            gen2 = getattr(self.llm, "generate", None)
            if callable(gen2):
                r = asyncio.run(gen2(prompt=user, system_prompt=system))
                return str(r or "").strip()
        except Exception:
            pass
        return ""


# --------------------------------------------------------------------------
# Main class
# --------------------------------------------------------------------------
class VerificationLayer:
    def __init__(self, llm, verbose: bool = False):
        self.a = _Adapter(llm)
        self.verbose = verbose

    # ---------------- 1. decompose ----------------
    def decompose(self, query: str) -> List[str]:
        sys_p = (
            "You break a question into the smallest sub-questions whose "
            "answers, combined, would answer the original. Output ONLY a "
            "JSON array of strings. 1-5 items. No prose, no markdown."
        )
        raw = self.a.ask(sys_p, f"Question: {query}\n\nSub-questions (JSON array):",
                         max_tokens=300)
        return self._parse_str_list(raw) or [query]

    # ---------------- 2. draft ----------------
    def draft(self, query: str, sub_qs: List[str],
              context: str = "") -> str:
        sys_p = (
            "You are Neo. Answer the user's question directly and factually. "
            "If CONTEXT is provided, ground every claim in it. "
            "If you are not sure, say so — never invent facts. "
            "Be concise; no filler."
        )
        sq = "\n".join(f"- {q}" for q in sub_qs)
        user = f"QUESTION: {query}\n\nSUB-QUESTIONS:\n{sq}\n\nCONTEXT:\n{context or '(none)'}\n\nAnswer:"
        return self.a.ask(sys_p, user, max_tokens=1200)

    # ---------------- 3. critique ----------------
    def critique(self, query: str, draft: str,
                 context: str = "") -> Dict[str, Any]:
        sys_p = (
            "You are a strict reviewer. Given a QUESTION, a CONTEXT, and a "
            "DRAFT answer, output ONLY a JSON object:\n"
            "{\n"
            '  "answers_question": true|false,\n'
            '  "facts_grounded":    true|false,\n'
            '  "is_complete":       true|false,\n'
            '  "is_honest":         true|false,\n'
            '  "problems":          ["...", "..."],\n'
            '  "needs_revision":    true|false\n'
            "}\n"
            "Rules:\n"
            "  facts_grounded=false if the draft states facts NOT in CONTEXT "
            "and not widely known.\n"
            "  is_honest=false if the draft is confident about something it "
            "should be uncertain about.\n"
            "  needs_revision=true if any of the above is false OR if there "
            "is a material problem.\n"
            "No prose, no markdown."
        )
        user = (
            f"QUESTION: {query}\n\n"
            f"CONTEXT:\n{context or '(none)'}\n\n"
            f"DRAFT:\n{draft}\n\n"
            f"Review (JSON only):"
        )
        raw = self.a.ask(sys_p, user, max_tokens=400)
        return self._parse_json(raw) or {
            "answers_question": True, "facts_grounded": True,
            "is_complete": True, "is_honest": True,
            "problems": ["critique unparseable"], "needs_revision": False,
        }

    # ---------------- 4. revise ----------------
    def revise(self, query: str, draft: str, crit: Dict[str, Any],
               context: str = "") -> str:
        sys_p = (
            "You are Neo. You wrote a draft answer. A reviewer flagged "
            "problems. Rewrite the answer fixing every problem while keeping "
            "what was correct. Ground every claim in CONTEXT. Be honest "
            "about uncertainty. Output only the revised answer."
        )
        probs = "\n".join(f"- {p}" for p in crit.get("problems", []))
        user = (
            f"QUESTION: {query}\n\n"
            f"CONTEXT:\n{context or '(none)'}\n\n"
            f"ORIGINAL DRAFT:\n{draft}\n\n"
            f"PROBLEMS FLAGGED:\n{probs}\n\n"
            f"Revised answer:"
        )
        return self.a.ask(sys_p, user, max_tokens=1200)

    # ---------------- 5. confidence ----------------
    def confidence(self, crit: Dict[str, Any], n_problems: int) -> float:
        """0.0 to 1.0, from the boolean flags in the critique."""
        c = 0.0
        if crit.get("answers_question"): c += 0.30
        if crit.get("facts_grounded"):   c += 0.30
        if crit.get("is_complete"):      c += 0.20
        if crit.get("is_honest"):        c += 0.20
        # small penalty for unsolved problems
        c -= min(0.15, n_problems * 0.05)
        return round(max(0.0, min(1.0, c)), 3)

    # ---------------- orchestrate ----------------
    def reason(self, query: str, context: str = "") -> Dict[str, Any]:
        t0 = time.time()
        steps: List[str] = []

        sub_qs = self.decompose(query)
        steps.append(f"decompose:{len(sub_qs)}")

        d = self.draft(query, sub_qs, context)
        steps.append("draft")

        crit = self.critique(query, d, context)
        steps.append(f"critique:revise={crit.get('needs_revision')}")

        if crit.get("needs_revision"):
            d2 = self.revise(query, d, crit, context)
            # verify again
            crit2 = self.critique(query, d2, context)
            steps.append(f"revise:revise={crit2.get('needs_revision')}")
            if crit2.get("needs_revision") and len(steps) < MAX_STEPS:
                d3 = self.revise(query, d2, crit2, context)
                d = d3
                crit = crit2
            else:
                d = d2
                crit = crit2

        conf = self.confidence(crit, len(crit.get("problems", [])))

        # If confidence is low, add an honesty footer
        answer = d
        if conf < 0.4:
            answer = (d + "\n\n"
                      "[low confidence — verify independently. "
                      f"flags: {', '.join(crit.get('problems', [])[:3]) or 'none'}]")
        elif conf < 0.65:
            answer = d + "\n\n[medium confidence]"

        return {
            "answer": answer,
            "raw_draft": d,
            "critique": crit,
            "confidence": conf,
            "sub_questions": sub_qs,
            "steps": steps,
            "elapsed_ms": int((time.time() - t0) * 1000),
        }

    # ---------------- helpers ----------------
    @staticmethod
    def _parse_str_list(raw: str) -> Optional[List[str]]:
        if not raw:
            return None
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [str(x) for x in arr if str(x).strip()]
        except Exception:
            pass
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group(0))
                if isinstance(arr, list):
                    return [str(x) for x in arr if str(x).strip()]
            except Exception:
                pass
        # last resort: lines starting with -
        lines = [re.sub(r"^\s*[-*\d.]+\s*", "", ln).strip()
                 for ln in raw.splitlines() if ln.strip()]
        return lines[:5] or None

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        s = raw.strip()
        if "```json" in s:
            s = s.split("```json")[1].split("```")[0]
        elif "```" in s:
            s = s.split("```")[1].split("```")[0]
        try:
            return json.loads(s.strip())
        except Exception:
            m = re.search(r"\{.*\}", s, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return None
        return None


# --------------------------------------------------------------------------
# Convenience: build from env
# --------------------------------------------------------------------------
def from_env(llm=None) -> Optional["VerificationLayer"]:
    """Return a VerificationLayer if NEO_REASONING_MODE=verify, else None."""
    if os.getenv("NEO_REASONING_MODE", "").lower() != "verify":
        return None
    if llm is None:
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
        except Exception as e:
            log.warning("[verification] cannot build LocalLLM: %s", e)
            return None
    return VerificationLayer(llm)
'''
(root / "core" / "reasoning" / "verification.py").write_text(verif, encoding="utf-8")
print("[ok] core/reasoning/verification.py")

# ============================================================
# 4. Wire verification into neo_brain.py as opt-in
# ============================================================
nb = root / "core" / "services" / "neo_brain.py"
if nb.exists():
    src = nb.read_text(encoding="utf-8")
    # insert a check in respond() after command passthrough and before skill preflight
    anchor = (
        '        # --- ADDED: Deterministic skill pre-flight --------------------------\n'
        '        # Math / date / uuid / reverse / translate / similarity / summary /'
    )
    injection = (
        '        # --- VERIFICATION MODE (opt-in via NEO_REASONING_MODE=verify) ------\n'
        '        # When enabled, every non-personal, non-skill query gets the\n'
        '        # decompose->draft->critique->revise loop before returning.\n'
        '        _mode = os.getenv("NEO_REASONING_MODE", "").lower()\n'
        '        if _mode == "verify" and not _is_personal_query(user_input):\n'
        '            try:\n'
        '                from core.reasoning.verification import VerificationLayer\n'
        '                layer = VerificationLayer(self.llm)\n'
        '                out = layer.reason(user_input)\n'
        '                self.agent_calls += 1\n'
        '                self.conversation_history.append({\n'
        '                    "role": "assistant",\n'
        '                    "content": out["answer"],\n'
        '                    "mode": "VERIFY",\n'
        '                    "personality": "analyst",\n'
        '                    "confidence": out["confidence"],\n'
        '                })\n'
        '                print(f"[NeoBrain] Verification mode: conf={out[\'confidence\']} "\n'
        '                      f"steps={out[\'steps\']}")\n'
        '                return self._format_response(\n'
        '                    out["answer"],\n'
        '                    {"mode": "VERIFY", "personality": "analyst"},\n'
        '                )\n'
        '            except Exception as _e:\n'
        '                print(f"[NeoBrain] Verification layer failed, falling through: {_e}")\n'
        '        # --- end verification mode -----------------------------------------\n'
        '\n'
    )
    if anchor in src and "VerificationLayer" not in src:
        src = src.replace(anchor, injection + anchor, 1)
        nb.write_text(src, encoding="utf-8")
        print("[ok] wired verification mode into neo_brain.py")
    elif "VerificationLayer" in src:
        print("[skip] neo_brain.py already has verification hookup")
    else:
        print("[warn] neo_brain anchor not found — verification not wired")
else:
    print("[warn] core/services/neo_brain.py not found")

# ============================================================
# 5. Add NEO_REASONING_MODE docs to .env.example
# ============================================================
env_ex = root / ".env.example"
existing = env_ex.read_text(encoding="utf-8") if env_ex.exists() else ""
addition = """

# ============ Reasoning mode ============
# NEO_REASONING_MODE=verify
#   Every non-skill query goes through:
#     decompose -> draft -> critique -> revise -> confidence
#   Slower (3-5 LLM calls per query) but self-checked.
#   Leave unset for the current fast path.
# NEO_REASONING_MODE=
"""
if "NEO_REASONING_MODE" not in existing:
    env_ex.write_text(existing + addition, encoding="utf-8")
    print("[ok] documented NEO_REASONING_MODE in .env.example")

# ============================================================
# 6. Compile everything
# ============================================================
for p in [root/"test_new_features.py",
          root/"test_nosignup_tools.py",
          root/"core"/"reasoning"/"__init__.py",
          root/"core"/"reasoning"/"verification.py",
          root/"core"/"services"/"neo_brain.py"]:
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.relative_to(root)} compiles")
    except py_compile.PyCompileError as e:
        print(f"[fail] {p.relative_to(root)}: {e}")
        raise SystemExit(1)

print()
print("=" * 72)
print("  THREE DELIVERABLES READY")
print("=" * 72)
print()
print("1. Fixed 2 test bugs:")
print("   python test_new_features.py")
print()
print("2. Per-tool validator (245 tools):")
print("   python test_nosignup_tools.py                    # schema only, fast")
print("   python test_nosignup_tools.py --all              # print every tool")
print("   python test_nosignup_tools.py --live             # + URL reachability")
print("   python test_nosignup_tools.py --live --all       # full report")
print()
print("3. Reasoning layer (decompose/critique/revise):")
print("   echo NEO_REASONING_MODE=verify >> .env")
print("   # then restart launcher — every non-skill query self-checks")
print("   # or test directly:")
print("   python -c \"from core.local_llm import LocalLLM; \\")
print("     from core.reasoning.verification import VerificationLayer; \\")
print("     import json; out = VerificationLayer(LocalLLM()).reason(\\")
print("       'What is the capital of Burkina Faso and who leads it?'); \\")
print("     print(json.dumps(out, indent=2)[:800])\"")