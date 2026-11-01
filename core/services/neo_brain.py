"""
core/services/neo_brain.py

Wraps FundiBrain with mode routing, personality engine, 
cognitive core, synthesis - AND agent orchestration.
"""

import os
import re
import sys
import asyncio
from typing import Dict, Optional, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.services.ollama_service import ask_ollama
from core.local_llm import LocalLLM


# ============================================================================
# MODE ROUTER
# ============================================================================


# -------- shell-command detector --------
_SHELL_PREFIXES = (
    "python ", "python3 ", "py ",
    "pip ", "pip3 ", "npm ", "npx ", "yarn ", "pnpm ",
    "docker ", "docker-compose ", "git ",
    "cargo ", "rustc ", "go ", "node ",
    "uvicorn ", "gunicorn ", "flask ", "django-admin ",
    "pytest ", "ruff ", "mypy ",
    "curl ", "wget ", "ssh ", "scp ", "rsync ",
    "cat ", "ls ", "dir ", "cd ",
    "echo ", "touch ", "mkdir ", "rm ", "cp ", "mv ",
    "$ ",
)


def _looks_like_shell_command(text: str) -> bool:
    if not text:
        return False
    low = text.strip().lower()
    for p in _SHELL_PREFIXES:
        if low.startswith(p.lower()):
            return True
    if re.search(r"\bpython3?\s+-c\s+['\"]", text):
        return True
    return False


_SHELL_REPLY = (
    "That looks like a shell command. Run it in PowerShell (not here):\n\n"
    "    {cmd}\n\n"
    "If you want Neo to execute shell commands for you, use:\n"
    "    > agent run shell: {cmd}\n"
    "(that routes to SystemAgent, which runs commands locally)"
)


class ModeRouter:
    PERSONAL_SIGNALS = {
        'i feel', 'i think', 'should i', 'my mom', 'my dad', 'my job',
        'my wife', 'my husband', 'worried about', 'stressed',
        'dream', 'remember when', 'advice', 'lonely', 'happy that',
        'sad that', 'afraid', 'i want to', 'confused', 'unsure'
    }

    TOOL_SIGNALS = {
        'search', 'look up', 'find online', 'latest news', 'current',
        'weather', 'stock price', 'github', 'code this', 'pdf', 'ocr',
        'analyze', 'compare', 'summarize', 'schedule', 'email', 'notify'
    }

    AGENT_SIGNALS = {
        'and then', 'after that', 'also', 'what about', 'additionally',
        'plus', 'find', 'then', 'next', 'finally', 'first', 'second'
    }

    def __init__(self, local_llm: LocalLLM):
        self.llm = local_llm

    def classify_intent(self, user_input: str) -> str:
        text = user_input.lower()
        if any(s in text for s in self.AGENT_SIGNALS) and len(text) > 30:
            return "AGENT"
        if any(s in text for s in self.TOOL_SIGNALS):
            return "FACTUAL"
        if any(s in text for s in self.PERSONAL_SIGNALS):
            return "EMOTIONAL"
        if any(s in text for s in ['remember when', 'what did i tell you']):
            return "BIOGRAPHICAL"
        if any(s in text for s in ['should i', 'plan', 'consider']):
            return "PLANNING"
        if any(s in text for s in ['code', 'debug', 'function', 'error']):
            return "TECHNICAL"
        return "AMBIGUOUS"

    def decide_mode(self, user_input: str) -> Dict:
        intent = self.classify_intent(user_input)
        if intent == "AGENT":
            return {
                'mode': 'AGENT',
                'intent': intent,
                'use_orchestrator': True,
                'use_tools': True,
                'personality': 'analyst'
            }
        elif intent in ("EMOTIONAL", "BIOGRAPHICAL", "PLANNING"):
            return {
                'mode': 'PERSONAL',
                'intent': intent,
                'use_orchestrator': False,
                'use_tools': False,
                'personality': 'mentor' if intent == 'PLANNING' else 'friendly'
            }
        elif intent == "TECHNICAL":
            return {
                'mode': 'TOOL_ASSISTED',
                'intent': intent,
                'use_orchestrator': True,
                'use_tools': True,
                'personality': 'strict'
            }
        else:
            return {
                'mode': 'HYBRID',
                'intent': intent,
                'use_orchestrator': True,
                'use_tools': True,
                'personality': 'professional'
            }


# ============================================================================
# PERSONALITY ENGINE
# ============================================================================

class PersonalityEngine:
    PROFILES = {
        "friendly": {
            "system": "You are warm, encouraging, and genuinely curious. Use gentle humor. Validate struggles.",
            "temperature": 0.8
        },
        "professional": {
            "system": "You are composed, articulate, and precise. Structure complex thoughts clearly.",
            "temperature": 0.4
        },
        "strict": {
            "system": "You are direct and intellectually rigorous. Challenge weak reasoning. No filler.",
            "temperature": 0.3
        },
        "mentor": {
            "system": "You are a wise, patient mentor. Use the Socratic method. Guide discovery.",
            "temperature": 0.6
        },
        "analyst": {
            "system": "You are a systems thinker. Present multiple scenarios. Quantify uncertainty.",
            "temperature": 0.5
        },
        "creative": {
            "system": "You are imaginative and associative. Make unexpected connections.",
            "temperature": 0.9
        }
    }

    def __init__(self, default: str = "friendly"):
        self.active = self.PROFILES.get(default, self.PROFILES["friendly"])

    def set_personality(self, name: str) -> bool:
        if name in self.PROFILES:
            self.active = self.PROFILES[name]
            return True
        return False


# ============================================================================
# COGNITIVE CORE
# ============================================================================

class CognitiveCore:
    def __init__(self):
        # FIXED: was "qwen2.5:7b" but the machine only has "qwen2.5:1.5b".
        # Every cognitive call was returning empty strings because Ollama
        # couldn't load the missing model.
        self.model = "qwen2.5:1.5b"

    async def reason(self, user_input: str, context: Dict, depth: int = 2) -> Dict:
        understanding = await self._step_understand(user_input, context)
        perspectives = await self._step_perspectives(user_input, understanding) if depth >= 2 else None
        synthesis = await self._step_synthesize(user_input, understanding, perspectives, context)
        return {
            'synthesis': synthesis,
            'steps': ['understand', 'perspectives', 'synthesize'] if perspectives else ['understand', 'synthesize'],
            'confidence': 0.7
        }

    async def _step_understand(self, query: str, context: Dict) -> str:
        prompt = "Analyze what the user REALLY wants. Be concise.\nUser: \"" + query + "\"\nRespond with ONLY the core question and emotional subtext. 2 sentences max."
        return await ask_ollama(prompt, model=self.model)

    async def _step_perspectives(self, query: str, understanding: str) -> str:
        prompt = "Generate 2 brief alternative perspectives.\nUnderstanding: " + understanding + "\nUser: \"" + query + "\"\nFormat: Perspective 1: ... Perspective 2: ..."
        return await ask_ollama(prompt, model=self.model)

    async def _step_synthesize(self, query: str, understanding: str, perspectives: Optional[str], context: Dict) -> str:
        pers_text = "\nPerspectives: " + perspectives if perspectives else ""
        prompt = "Synthesize into a direct, helpful response.\nUser: \"" + query + "\" Core issue: " + understanding + pers_text + "\nRespond as the user's thinking partner. Be honest about uncertainty."
        return await ask_ollama(prompt, model=self.model)


# ============================================================================
# SYNTHESIS ENGINE
# ============================================================================
# NOTE: kept for backwards compatibility. No longer on the hot path.
# The old flow did: brain.respond() → cognitive.reason() → synthesize(brain, cognitive)
# That produced noise like "Answer A: / Answer B: Run 'ollama serve'".
# Now the orchestrator's ReAct loop does the synthesis work via tools + LLM.

class SynthesisEngine:
    async def synthesize(self, user_input: str, cognitive_result: Dict, tool_output: Optional[str], mode: str) -> Dict:
        cognitive = cognitive_result.get('synthesis', '')
        if not tool_output or mode == 'PERSONAL':
            return {
                'response': cognitive,
                'source': 'cognitive_only',
                'confidence': cognitive_result.get('confidence', 0.7)
            }

        prompt = "Pick the better answer or blend them.\nQuestion: " + user_input + "\nAnswer A (reasoned): " + cognitive + "\nAnswer B (tools): " + str(tool_output) + "\nRespond with the best answer. Do not mention A or B."
        blended = await ask_ollama(prompt, model="qwen2.5:1.5b")
        return {
            'response': blended,
            'source': 'blended',
            'confidence': 0.8
        }


# ============================================================================
# DETERMINISTIC SKILL PRE-FLIGHT (ADDED)
# ============================================================================
# Rationale:
#   Math, date, uuid, reverse-string, translate, language detect, similarity,
#   summary, solve, and currency queries have deterministic answers and
#   matching lazy tools. If we let the LLM decide, it usually just computes
#   the answer itself — burning tokens, hitting rate limits, and never
#   triggering the lazy tool. Instead we pattern-match these queries up
#   front and dispatch directly to the skill. Zero LLM calls for these.
#
# Anything that doesn't match falls through to the normal flow, so
# "who is the president of Kenya" still goes to Tavily and
# "what's the weather" still goes to the orchestrator.
# ---------------------------------------------------------------------------

# FIXED: extended with self-referential patterns. Previously "who are you"
# fell through to Tavily's factual bypass and returned The Who's song.
_PERSONAL_HINTS = re.compile(
    r"\b(i feel|i think|i'm|i am|my mom|my dad|my wife|my husband|"
    r"worried about|stressed|lonely|sad|afraid|confused|unsure|"
    r"should i|advice|remember when|"
    r"who are you|what are you|what is your name|what can you do|"
    r"tell me about yourself|introduce yourself|your capabilities)\b",
    re.IGNORECASE,
)


def _is_personal_query(text: str) -> bool:
    """Detect queries that should never be short-circuited by a skill."""
    return bool(_PERSONAL_HINTS.search(text or ""))


# (compiled_pattern, tool_key, extractor) — extractor returns kwargs for the tool
_SKILL_ROUTES = [
    # "what is 15% of 240"  →  math  {expression: "15/100*240"}
    (re.compile(
        r"^\s*(?:what(?:'s|\s+is)\s+|calculate\s+|compute\s+|evaluate\s+)?"
        r"(-?\d+(?:\.\d+)?\s*%\s*of\s*-?\d+(?:\.\d+)?)\s*\??\s*$",
        re.IGNORECASE,
    ), "math", lambda m: {"expression": re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"\1/100*", m.group(1))}),

    # "what is 5 + 3" / "12 * 4" / "100/5"
    (re.compile(
        r"^\s*(?:what(?:'s|\s+is)\s+|calculate\s+|compute\s+|evaluate\s+)?"
        r"(-?\d+(?:\.\d+)?(?:\s*[+\-*/]\s*-?\d+(?:\.\d+)?)+)\s*\??\s*$",
        re.IGNORECASE,
    ), "math", lambda m: {"expression": m.group(1)}),

    # "what is today's date" / "what's the date today" / "what day is it"
    (re.compile(
        r"^\s*(?:what(?:'s|\s+is)\s+)?(?:the\s+)?"
        r"(?:today(?:'s)?\s+(?:date|day)|date\s+today|day\s+today|"
        r"what\s+day\s+is\s+it)\s*\??\s*$",
        re.IGNORECASE,
    ), "date", lambda m: {"query": "today"}),

    # "tomorrow's date"
    (re.compile(r"^\s*(?:what(?:'s|\s+is)\s+)?tomorrow(?:'s)?\s+date\s*\??\s*$", re.IGNORECASE),
     "date", lambda m: {"query": "tomorrow"}),

    # "yesterday's date"
    (re.compile(r"^\s*(?:what(?:'s|\s+is)\s+)?yesterday(?:'s)?\s+date\s*\??\s*$", re.IGNORECASE),
     "date", lambda m: {"query": "yesterday"}),

    # "uuid" / "generate a uuid"
    (re.compile(r"^\s*(?:generate\s+|give\s+me\s+|make\s+)?(?:a\s+|an\s+)?uuid\s*\??\s*$", re.IGNORECASE),
     "uuid", lambda m: {}),

    # "reverse a string hello" / "reverse 'hello world'"
    (re.compile(r"^\s*reverse\s+(?:a\s+|the\s+)?string\s+(.+?)\s*$", re.IGNORECASE),
     "text_transform", lambda m: {"text": m.group(1).strip("'\""), "operation": "reverse"}),

    # --- ADDED routes for agent-prefixed queries ---

    # "translate hello to swahili" / "translate 'bonjour' to english"
    (re.compile(r"^\s*translate\s+(.+?)\s+to\s+([a-zA-Z]+)\s*$", re.IGNORECASE),
     "translate", lambda m: {"text": m.group(1).strip("'\""), "src": "auto", "tgt": m.group(2).lower()}),

    # "detect language: X" / "what language is X" / "which language: X"
    (re.compile(r"^\s*(?:detect\s+language[:\s]+|what\s+language\s+is\s+|which\s+language[:\s]+)(.+)$", re.IGNORECASE),
     "language_detect", lambda m: {"text": m.group(1).strip("'\"")}),

    # "similarity between X and Y" / "edit distance between X and Y"
    (re.compile(r"^\s*(?:similarity|edit\s+distance|levenshtein)\s+between\s+(.+?)\s+and\s+(.+?)\s*$", re.IGNORECASE),
     "levenshtein", lambda m: {"a": m.group(1).strip("'\""), "b": m.group(2).strip("'\"")}),

    # "summarize: X" / "summarize this: X" / "summarize X"
    (re.compile(r"^\s*summari[sz]e(?:\s+this)?[:\s]+(.+)$", re.IGNORECASE | re.DOTALL),
     "summary", lambda m: {"text": m.group(1).strip(), "max_sentences": 3}),

    # "solve x**2 - 4" / "solve equation x+2=0"  → sympy
    (re.compile(r"^\s*solve\s+(?:equation\s+)?(.+)$", re.IGNORECASE),
     "math", lambda m: {"expression": "solve " + m.group(1).strip()}),

    # "100 usd to kes" / "convert 100 usd to kes" / "convert 50 eur to usd"
    (re.compile(r"^\s*(?:convert\s+)?(\d+(?:\.\d+)?)\s+([a-zA-Z]{3})\s+to\s+([a-zA-Z]{3})\s*$", re.IGNORECASE),
     "currency_convert", lambda m: {"amount": float(m.group(1)), "from": m.group(2).upper(), "to": m.group(3).upper()}),
]


def _try_skill_pre_flight(text: str, orchestrator) -> Optional[str]:
    """
    If the query matches a known skill pattern, call that skill directly
    and return its result as a string. Otherwise return None so the caller
    can continue with the normal orchestrator flow.
    """
    if not text or not text.strip():
        return None
    for pattern, tool_key, extractor in _SKILL_ROUTES:
        m = pattern.match(text)
        if not m:
            continue
        tool = orchestrator.plugins.get(tool_key)
        if tool is None:
            # Skill not registered — let normal flow handle it.
            return None
        try:
            kwargs = extractor(m)
            result = tool(**kwargs)
            if result is None:
                return None
            result_str = str(result)
            # If the lazy loader or the skill returned an error, bail to normal flow.
            if result_str.startswith("[Tool error]") or result_str.startswith("[Error]"):
                return None
            # --- FIXED: unwrap a much wider set of dict keys, plus fall back
            # to single-entry dicts. Skills return {"uuid": "..."},
            # {"date": "..."}, {"translated": "..."}, {"distance": N, ...},
            # {"summary": "..."}, {"converted": N, ...}, {"detected_language":
            # "..."}, and many others. The old list only covered 5 keys.
            if isinstance(result, dict):
                for key in (
                    "result", "answer", "text", "output", "response",
                    "uuid", "date", "datetime", "time", "value",
                    "reversed", "corrected", "generated", "converted",
                    "sequence", "emails", "entities", "matches",
                    "summary", "counts", "distance", "similarity",
                    "min", "max", "detected_language", "translated",
                ):
                    if key in result and result[key] is not None:
                        return str(result[key])
                # Single-entry dict: return its only value
                if len(result) == 1:
                    return str(next(iter(result.values())))
            return result_str
        except Exception as e:
            print(f"[NeoBrain] Skill pre-flight '{tool_key}' failed: {e}")
            return None
    return None


# ============================================================================
# NEO BRAIN WRAPPER - WITH ORCHESTRATOR SUPPORT
# ============================================================================

class NeoBrainWrapper:
    def __init__(self, fundibrain, llm: LocalLLM, orchestrator=None):
        self.brain = fundibrain
        self.llm = llm
        self.orchestrator = orchestrator
        self.conversation_history: List[Dict] = []
        self.personalities = PersonalityEngine("mentor")
        self.cognitive = CognitiveCore()
        self.synthesis = SynthesisEngine()
        self.total_calls = 0
        self.cognitive_only_calls = 0
        self.agent_calls = 0
        self.tool_assisted_calls = 0

    async def respond(self, user_input: str) -> str:
        self.total_calls += 1
        self.conversation_history.append({"role": "user", "content": user_input})

        # --- shell-command short-circuit -----------------------------------
        if _looks_like_shell_command(user_input):
            reply = _SHELL_REPLY.format(cmd=user_input.strip())
            self.conversation_history.append({
                "role": "assistant", "content": reply,
                "mode": "SHELL_HINT", "personality": "professional",
            })
            return self._format_response(
                reply,
                {"mode": "SHELL_HINT", "personality": "professional"},
            )

        # --- URL learning fast path -----------------------------------------
        if user_input.strip().startswith(("http://", "https://")):
            try:
                result = self.brain.learn_from_url(user_input.strip())
                self.conversation_history.append({
                    "role": "assistant",
                    "content": str(result),
                    "mode": "URL_LEARN",
                    "personality": "professional",
                })
                return self._format_response(
                    str(result),
                    {"mode": "URL_LEARN", "personality": "professional"},
                )
            except Exception as e:
                print(f"[NeoBrain] URL learn failed: {e}")
        # --- end URL fast path ----------------------------------------------

        # --- Command passthrough --------------------------------------------
        # Neo-native commands ("start auto", "show context", "list goals",
        # "clear context", "stats", etc.) should go straight to FundiBrain's
        # handle_commands(), NOT through the LLM. Route them here so the
        # orchestrator never sees them.
        _COMMAND_PREFIXES = (
            "start auto", "stop auto",
            "show context", "clear context",
            "list goals", "run goals", "goal ",
            "stats", "memory ", "db test", "debug",
            "train ", "voice", "github ", "notify ", "vision ",
            "scan", "models",
        )
        _low = user_input.lower().strip()
        if any(_low == p.strip() or _low.startswith(p) for p in _COMMAND_PREFIXES):
            try:
                cmd_result = self.brain.respond(user_input)
                if cmd_result:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": str(cmd_result),
                        "mode": "COMMAND",
                        "personality": "professional",
                    })
                    return self._format_response(
                        str(cmd_result),
                        {"mode": "COMMAND", "personality": "professional"},
                    )
            except Exception as e:
                print(f"[NeoBrain] Command passthrough failed: {e}")
        # --- end command passthrough ----------------------------------------

        # --- VERIFICATION MODE (opt-in via NEO_REASONING_MODE=verify) ------
        # When enabled, every non-personal, non-skill query gets the
        # decompose->draft->critique->revise loop before returning.
        _user_low = user_input.strip().lower()
        _force_fast = _user_low.startswith("/fast ")
        _force_verify = _user_low.startswith("/verify ")
        if _force_fast:
            user_input = user_input[6:].strip()
        elif _force_verify:
            user_input = user_input[8:].strip()
        _mode = os.getenv("NEO_REASONING_MODE", "").lower()
        _use_verify = _force_verify or (_mode == "verify" and not _force_fast)
        if _use_verify and not _is_personal_query(user_input):
            try:
                from core.reasoning.verification import VerificationLayer
                layer = VerificationLayer(self.llm)
                out = layer.reason(user_input)
                self.agent_calls += 1
                self.conversation_history.append({
                    "role": "assistant",
                    "content": out["answer"],
                    "mode": "VERIFY",
                    "personality": "analyst",
                    "confidence": out["confidence"],
                })
                print(f"[NeoBrain] Verification mode: conf={out['confidence']} "
                      f"steps={out['steps']}")
                return self._format_response(
                    out["answer"],
                    {"mode": "VERIFY", "personality": "analyst"},
                )
            except Exception as _e:
                print(f"[NeoBrain] Verification layer failed, falling through: {_e}")
        # --- end verification mode -----------------------------------------

        # --- ADDED: Deterministic skill pre-flight --------------------------
        # Math / date / uuid / reverse / translate / similarity / summary /
        # solve / currency queries have deterministic answers and matching
        # lazy tools. Dispatch to the skill directly without ever touching
        # the LLM. Skipped for personal queries ("i feel sad", "who are you")
        # so those still route through the cognitive path below.
        if self.orchestrator is not None and not _is_personal_query(user_input):
            skill_result = _try_skill_pre_flight(user_input, self.orchestrator)
            if skill_result is not None:
                self.tool_assisted_calls += 1
                self.conversation_history.append({
                    "role": "assistant",
                    "content": skill_result,
                    "mode": "SKILL",
                    "personality": "professional"
                })
                print(f"[NeoBrain] Skill pre-flight fired for: {user_input!r}")
                return self._format_response(
                    skill_result,
                    {"mode": "SKILL", "personality": "professional"}
                )
        # --- end skill pre-flight -------------------------------------------

        router = ModeRouter(self.llm)
        decision = router.decide_mode(user_input)
        self.personalities.set_personality(decision['personality'])

        # --- PERSONAL: pure cognitive, no tools -----------------------------
        if decision['mode'] == 'PERSONAL':
            self.cognitive_only_calls += 1
            try:
                cognitive = await self.cognitive.reason(
                    user_input,
                    {'mode': 'PERSONAL', 'personality': decision['personality']},
                    depth=3
                )
                response = cognitive.get('synthesis') or self.brain.respond(user_input)
            except Exception as e:
                print(f"[NeoBrain] Cognitive failed: {e}")
                response = self.brain.respond(user_input)

        # --- ALL OTHER MODES: route through the ReAct orchestrator ----------
        elif self.orchestrator is not None:
            self.agent_calls += 1
            try:
                response = await self.orchestrator.run(
                    user_input,
                    conversation_history=self.conversation_history
                )
                if os.getenv('NEO_DEBUG'):
                    trace = self.orchestrator.get_execution_log()
                    print("[NeoBrain] Orchestrator trace: " + str(len(trace)) + " steps")
            except Exception as e:
                print(f"[NeoBrain] Orchestrator failed: {e}")
                response = self.brain.respond(user_input)

        # --- No orchestrator: last-resort fallback --------------------------
        else:
            response = self.brain.respond(user_input)

        self.conversation_history.append({
            "role": "assistant",
            "content": response,
            "mode": decision['mode'],
            "personality": decision['personality']
        })

        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-20:]

        return self._format_response(response, decision)

    def _format_response(self, response: str, decision: Dict) -> str:
        text = response.strip()
        if decision.get('personality') == 'strict':
            text = text.strip()
        if os.getenv('NEO_DEBUG'):
            text += "\n\n[debug: mode=" + decision['mode'] + " | personality=" + decision['personality'] + " | calls=" + str(self.total_calls) + "]"
        return text

    def get_stats(self) -> Dict:
        if self.total_calls == 0:
            return {
                'tool_independence': 0.0,
                'total_calls': 0,
                'agent_calls': 0,
                'cognitive_only_calls': 0,
                'tool_assisted_calls': 0
            }
        return {
            'tool_independence': self.cognitive_only_calls / self.total_calls,
            'total_calls': self.total_calls,
            'agent_calls': self.agent_calls,
            'cognitive_only_calls': self.cognitive_only_calls,
            'tool_assisted_calls': self.tool_assisted_calls
        }

    def __getattr__(self, name):
        return getattr(self.brain, name)


def wrap_fundibrain(fundibrain, llm: LocalLLM, orchestrator=None) -> NeoBrainWrapper:
    """Wrap existing FundiBrain with Neo capabilities + optional orchestrator."""
    return NeoBrainWrapper(fundibrain, llm, orchestrator)