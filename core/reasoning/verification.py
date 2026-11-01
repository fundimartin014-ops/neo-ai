"""Verification reasoning loop.

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

# Phrases that signal the model itself was honest about limits. When any
# match, confidence is capped — otherwise the flags can all be True (the
# answer IS honest) while the underlying claim is still uncertain.
_HEDGE_PATTERNS = [
    # explicit "can't verify / don't know"
    r"\bcannot\s+(verify|confirm|be\s+sure|say|answer|determine)",
    r"\bcan'?t\s+(verify|confirm|be\s+sure|say|answer|determine)",
    r"\bi\s+(really\s+)?do(?:n'?t|\s+not)\s+know\b",
    r"\bi\s+cannot\s+(say|answer|determine)",
    # lack-of-information phrasings (this was the miss)
    r"\b(?:do|does)\s+not\s+have\s+(?:that|this|any)\s+information\b",
    r"\b(?:do|does)n'?t\s+have\s+(?:that|this|any)\s+information\b",
    r"\bi\s+(?:do\s+not|don'?t)\s+have\s+(?:that|this|any|access\s+to)",
    r"\bnot\s+(?:sure|certain|verified|confirmed|able\s+to\s+verify)",
    r"\bno\s+(?:current|up-to-date|reliable)\s+(?:source|information|data)",
    r"\bmy\s+information\s+may\s+be\s+(?:out\s+of\s+date|stale|incomplete)",
    # timestamped knowledge
    r"\bas\s+of\s+(?:the\s+)?(?:most\s+)?(?:recent|latest|current|my\s+last)",
    r"\bas\s+far\s+as\s+.{0,40}(available|known|public|training|record|aware)",
    r"\bup\s+to\s+(?:20\d\d|my\s+last)",
    r"\b(?:knowledge|training)\s+(?:cutoff|data)",
    r"\bsince\s+(?:my|the)\s+last",
    # conditionals on change
    r"\bif\s+(?:there\s+have\s+been|things\s+have|anything\s+has)\s+(?:changed|shifted)",
    r"\b(?:may|might|could)\s+have\s+(?:changed|shifted|been)",
    r"\bthe\s+situation\s+(?:could|may|might)\s+have\s+changed",
    r"\bafter\s+this\s+date",
    # generic uncertainty words
    r"\buncertain\b",
    r"\bunverified\b",
    r"\bnot\s+up\s+to\s+date\b",
]
def _hedge_cap(answer: str) -> Optional[float]:
    """Return a soft cap on confidence if the answer hedges, else None."""
    if not answer:
        return None
    t = answer.lower()
    # strongest: explicit "I don't know"
    if re.search(r"\bi\s+(really\s+)?don'?t\s+know\b", t):
        return 0.45
    for pat in _HEDGE_PATTERNS:
        if re.search(pat, t):
            return 0.70
    return None


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
    def confidence(self, crit: Dict[str, Any], n_problems: int,
                   answer: str = "") -> float:
        """0.0 to 1.0, from the boolean flags + hedging language in the answer."""
        c = 0.0
        if crit.get("answers_question"): c += 0.30
        if crit.get("facts_grounded"):   c += 0.30
        if crit.get("is_complete"):      c += 0.20
        if crit.get("is_honest"):        c += 0.20
        # small penalty for unsolved problems
        c -= min(0.15, n_problems * 0.05)
        # hedge cap: if the answer itself admits limits, don't pretend 1.0
        cap = _hedge_cap(answer)
        if cap is not None:
            c = min(c, cap)
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

        conf = self.confidence(crit, len(crit.get("problems", [])), answer=d)
        if self.verbose:
            _cap = _hedge_cap(d)
            print(f"[verification] hedge_cap={_cap} final_conf={conf}")
            if _cap is not None:
                import re as _re
                _t = d.lower()
                for _p in _HEDGE_PATTERNS:
                    if _re.search(_p, _t):
                        print(f"[verification]   matched: {_p}")
                        break

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
