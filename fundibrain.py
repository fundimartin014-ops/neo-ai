"""
fundibrain.py
NeoBrain core — reasoning router, self-critique, memory, and all commands.
Integrates with launcher.py and orchestrator.py for full agent capabilities.
Preserves all existing FundiBrain functionality.
"""

import os
import re
import json
import threading
import time
import sqlite3
import traceback
from difflib import get_close_matches
from urllib.request import Request, urlopen
from urllib.error import URLError
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.memory import (
    search_knowledge,
    remember,
    reinforce,
    penalize,
    store_correction
)
from core.web_search import search_web
from core.embedding_engine import EmbeddingEngine
from core.goal_manager import GoalManager
from core.planner import Planner
from core.browser_agent import BrowserAgent
from core.tool_registry import ToolRegistry
from core.execution_graph import ExecutionGraph
from core.tool_selector import ToolSelector
from core.verifier import Verifier

# Optional imports — gracefully degrade if missing
try:
    from core.meta_cognition import ReasoningRouter, SelfCritique, UnifiedMemory
    META_AVAILABLE = True
except ImportError:
    META_AVAILABLE = False
    ReasoningRouter = None
    SelfCritique = None
    UnifiedMemory = None

try:
    from core.orchestrator import NeoOrchestrator
    ORCH_AVAILABLE = True
except ImportError:
    ORCH_AVAILABLE = False
    NeoOrchestrator = None

try:
    from core.system_scanner import NeoSystemScanner
    SCAN_AVAILABLE = True
except ImportError:
    SCAN_AVAILABLE = False
    NeoSystemScanner = None

try:
    from core.tavily_search import tavily_search
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    tavily_search = None


# =====================================================================
# KIMI / MOONSHOT AI CLIENT
# =====================================================================
class KimiClient:
    def __init__(self, api_key=None, model="moonshot-v1-8k"):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = model
        self.base_url = "https://api.moonshot.cn/v1/chat/completions"
        self.available = bool(self.api_key)

    def generate(self, prompt, max_tokens=1024, temperature=0.3):
        if not self.available:
            return None
        try:
            payload = json.dumps({
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }).encode("utf-8")

            req = Request(
                self.base_url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[KIMI ERROR] {e}")
            return None


# =====================================================================
# SQLITE HELPER
# =====================================================================
def _get_db_conn():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brain.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_db_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_input TEXT, assistant_response TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()


# =====================================================================
# FUNDIBRAIN CLASS
# =====================================================================
class FundiBrain:

    def __init__(self, plugins=None, mini_llm=None):
        _init_db()
        self.plugins = plugins or []
        self.mini_llm = mini_llm
        self.embedder = EmbeddingEngine()
        self.goal_manager = GoalManager()
        self.planner = Planner()
        self.browser = BrowserAgent()
        self.tool_registry = ToolRegistry()
        self.tool_selector = ToolSelector()
        self.verifier = Verifier()

        self._register_tools()

        self.conversation = []
        self.max_context = 5
        self.last_question = None
        self.last_answer = None
        self.awaiting_correction = False
        self.vocab = self._build_vocab()
        self.running = False
        self.background_thread = None

        self.kimi = KimiClient()

        # NEW: Cloud-first reasoning router + critique + memory (optional)
        self.reasoning_router = None
        self.critique = None
        self.memory = None
        self.orchestrator = None
        self.scanner = None

        if META_AVAILABLE and mini_llm:
            try:
                self.reasoning_router = ReasoningRouter(mini_llm)
                self.critique = SelfCritique(mini_llm)
                self.memory = UnifiedMemory(self.embedder) if self.embedder else None
            except Exception as e:
                print(f"[FundiBrain] Meta-cognition init failed: {e}")

        if SCAN_AVAILABLE:
            try:
                self.scanner = NeoSystemScanner()
            except Exception as e:
                print(f"[FundiBrain] Scanner init failed: {e}")

        # Initialize orchestrator if plugins available
        if plugins:
            self._init_orchestrator()

        print("[Neo] STABLE CORE ONLINE")
        print("[Neo] JARVIS-CLASS AGENT ACTIVE")
        print("[Neo] TRUTH ENGINE V8 ACTIVE")
        if self.kimi.available:
            print("[Neo] KIMI INTEGRATION ACTIVE")
        if self.reasoning_router:
            print("[Neo] REASONING ROUTER ACTIVE")

    def _init_orchestrator(self):
        """Initialize ReAct orchestrator with all plugins."""
        if not ORCH_AVAILABLE:
            print("[FundiBrain] NeoOrchestrator not available.")
            return
        # --- FIXED: Guard against passing a LocalLLM where an LLMRouter is expected.
        # NeoOrchestrator._generate() calls self.llm.generate(system_prompt=...,
        # user_prompt=..., task_type=..., retries=...) via `await`. A LocalLLM is
        # sync and lacks those kwargs, so every iteration would pay a failed call.
        # The launcher injects a real orchestrator via wrap_fundibrain(); the
        # internal one is only built when the provided LLM actually looks like a
        # router (has `_select_model`, used by NeoOrchestrator._generate).
        llm = self.mini_llm
        looks_like_router = (
            llm is not None
            and hasattr(llm, "generate")
            and hasattr(llm, "_select_model")
        )
        if not looks_like_router:
            print("[FundiBrain] Skipping internal orchestrator "
                  "(llm_router not provided; launcher will inject one).")
            return
        # --- end FIXED guard ---
        try:
            plugin_dict = {}
            for p in self.plugins:
                raw_name = p.__class__.__name__.lower()
                name = raw_name.replace('plugin', '').replace('trainer', '').rstrip('_')
                if not name:
                    name = raw_name
                plugin_dict[name] = p

            self.orchestrator = NeoOrchestrator(
                llm_router=self.mini_llm,
                plugins=plugin_dict,
                memory_systems=self.memory,
                max_iterations=5
            )
            print("[Neo] AGENT ORCHESTRATOR ACTIVE")
        except Exception as e:
            print(f"[FundiBrain] Orchestrator init failed: {e}")

    # =====================================================================
    # COMMANDS
    # =====================================================================

    def handle_commands(self, text):
        try:
            t = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).strip()
            print(f"[DEBUG] handle_commands received: '{text}' -> normalized: '{t}'")

            if "start auto" in t:
                self.start_autonomous()
                return "Autonomous mode started"

            if "stop auto" in t:
                self.stop_autonomous()
                return "Autonomous mode stopped"

            if "show context" in t:
                return str(self.conversation)

            if "clear context" in t:
                self.conversation = []
                return "Context cleared."

            if "list goals" in t:
                return str(self.goal_manager.goals)

            if t.startswith("goal "):
                goal = text.strip()[5:].strip()
                if not goal:
                    return "Empty goal."
                self.goal_manager.add_goal(goal)
                return f"Goal added: {goal}"

            if "run goals" in t:
                if not getattr(self.goal_manager, "goals", None):
                    return "Goal queue is completely empty. Add one using 'goal <task>'."
                self.start_autonomous()
                return "Goal queue detected! Spinning up autonomous execution workers..."

            # NEW: Agent mode command
            if t.startswith("agent "):
                agent_query = text.strip()[6:].strip()
                if not agent_query:
                    return "Usage: agent <complex multi-step query>\nExamples:\n  agent research the latest AI breakthroughs and summarize\n  agent plan a trip to Tokyo with budget and schedule"
                return f"__AGENT_MODE__:{agent_query}"

            # NEW: Research command
            if t.startswith("research "):
                query = text[9:].strip()
                if not query:
                    return "Usage: research <topic>"
                if not TAVILY_AVAILABLE:
                    return "Tavily search not available. Install tavily-python."
                try:
                    result = tavily_search(query, search_depth="advanced", max_results=5, include_answer=True)
                    return result
                except Exception as e:
                    return f"Research error: {e}"

            # NEW: System scan
            if t == "scan":
                if not self.scanner:
                    return "System scanner not available."
                report = self.scanner.print_report()
                return "System scan complete. See console output above."

            # NEW: Stats with model info
            if t == "stats":
                lines = [
                    "NEO QUALITY METRICS",
                    "",
                    "FREE MODELS ACTIVE:",
                    "   deepseek/deepseek-r1:free — Reasoning (OpenRouter)",
                    "   qwen/qwen3-235b-a22b:free — Coding (OpenRouter)",
                    "   meta-llama/llama-4-maverick:free — Long Context (OpenRouter)",
                    "   llama-3.3-70b-versatile — Standard (Groq)",
                    "   qwen2.5:1.5b — Offline Fallback (Ollama)",
                    "",
                ]

                if self.critique:
                    try:
                        scores = self.critique.get_recent_scores(limit=50)
                        patterns = self.critique.get_failure_patterns(min_count=2)
                        reasoning_samples = self.critique.get_reasoning_stats(limit=3)

                        lines.extend([
                            f"   Accuracy:     {scores.get('accuracy', 'N/A')}/10",
                            f"   Completeness: {scores.get('completeness', 'N/A')}/10",
                            f"   Helpfulness:  {scores.get('helpfulness', 'N/A')}/10",
                            "",
                        ])

                        if reasoning_samples:
                            lines.append("Recent DeepSeek Reasoning:")
                            for r in reasoning_samples:
                                lines.append(f"   Q: {r['query'][:50]}...")
                                lines.append(f"   Thinking: {r['thinking'][:100]}...")
                                lines.append("")

                        if patterns:
                            lines.append("Recurring Failures:")
                            for p in patterns[:5]:
                                lines.append(f"   '{p['pattern']}' — {p['count']}x")
                    except Exception as e:
                        lines.append(f"Critique stats error: {e}")

                try:
                    import psutil
                    mem = psutil.virtual_memory()
                    lines.extend([
                        "",
                        f"RAM: {mem.percent}% ({mem.used/1024**3:.1f}GB / {mem.total/1024**3:.1f}GB)",
                        f"   Available: {mem.available/1024**3:.1f}GB",
                    ])
                except ImportError:
                    pass

                return "\n".join(lines)

            # NEW: Models command
            if t == "models":
                return """
ACTIVE FREE MODELS

  deepseek/deepseek-r1:free
     Provider: OpenRouter    Limit: 20 req/min
     Context: 64K            Use: Deep reasoning

  qwen/qwen3-235b-a22b:free
     Provider: OpenRouter    Limit: 20 req/min
     Context: 128K           Use: Code generation

  meta-llama/llama-4-maverick:free
     Provider: OpenRouter    Limit: 20 req/min
     Context: 1M             Use: Long documents

  llama-3.3-70b-versatile
     Provider: Groq          Limit: High (free tier)
     Context: 131K           Use: Standard/fast queries

  deepseek/deepseek-chat-v3-0324:free
     Provider: OpenRouter    Limit: 20 req/min
     Context: 64K             Use: Natural chat

  openai/gpt-oss-20b:free
     Provider: OpenRouter    Limit: 20 req/min
     Context: 131K           Use: Fast general tasks

  qwen2.5:1.5b (local Ollama)
     Provider: Local         Limit: Unlimited
     RAM: ~1.2GB             Use: Offline fallback
"""

            # NEW: Memory command
            if t.startswith("memory "):
                query = text[7:].strip()
                if self.memory:
                    try:
                        results = self.memory.query(query, top_k=5)
                        lines = ["Memory Search Results:"]
                        if results.get("semantic"):
                            lines.append("\nSemantic matches:")
                            for i, r in enumerate(results["semantic"][:3], 1):
                                lines.append(f"  {i}. {str(r)[:100]}...")
                        if results.get("structured"):
                            lines.append("\nRecent conversations:")
                            for i, r in enumerate(results["structured"][:3], 1):
                                lines.append(f"  {i}. Q: {r[0][:50]}... | A: {r[1][:50]}...")
                        return "\n".join(lines) if len(lines) > 1 else "No memory found."
                    except Exception as e:
                        return f"Memory query error: {e}"
                return "Memory system not initialized."

            # PLUGIN COMMANDS
            if t.startswith("train "):
                txt = text.strip()[6:]
                for p in self.plugins:
                    if hasattr(p, "train"):
                        return p.train(txt)
                return "No trainer plugin found."

            if t == "voice":
                for p in self.plugins:
                    if hasattr(p, "start"):
                        return p.start()
                return "Voice trainer not available."

            if t.startswith("github "):
                query = text.strip()[7:]
                for p in self.plugins:
                    if hasattr(p, "search_repos"):
                        return "\n".join(p.search_repos(query))
                return "GitHub plugin not available."

            if t.startswith("notify "):
                msg = text.strip()[7:]
                for p in self.plugins:
                    if hasattr(p, "notify"):
                        ok = p.notify(msg)
                        return "Notification sent." if ok else "Notification failed."
                return "Notification plugin not available."

            if t.startswith("vision "):
                path = text.strip()[7:]
                for p in self.plugins:
                    if hasattr(p, "analyze"):
                        return p.analyze(path)
                return "Vision plugin not available."

            if t == "db test":
                try:
                    conn = _get_db_conn()
                    c = conn.cursor()
                    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [r[0] for r in c.fetchall()]
                    conn.close()
                    return f"SQLite tables: {', '.join(tables)}"
                except Exception as e:
                    return f"DB error: {e}"

            # DEBUG PANEL
            if t == "debug":
                print("[DEBUG] Building debug panel...")

                llm_status = "Offline / Uninitialized"
                if self.mini_llm:
                    try:
                        model_name = getattr(self.mini_llm, 'model', 'Unknown')
                        llm_status = f"Operational ({model_name})"
                    except Exception as e:
                        llm_status = f"Check Failed: {e}"

                components = {
                    "Embedding Engine": "Online" if self.embedder else "Failed",
                    "Goal Manager": "Online" if self.goal_manager else "Failed",
                    "Planner": "Online" if self.planner else "Failed",
                    "Browser Agent": "Online" if self.browser else "Failed",
                    "Tool Registry": "Online" if self.tool_registry else "Failed",
                    "Tool Selector": "Online" if self.tool_selector else "Failed",
                    "Verifier": "Online" if self.verifier else "Failed",
                    "Kimi AI (Moonshot)": "Online" if (self.kimi and self.kimi.available) else "Offline / No API Key",
                    "Reasoning Router": "Online" if self.reasoning_router else "Offline",
                    "Self Critique": "Online" if self.critique else "Offline",
                    "Agent Orchestrator": "Online" if self.orchestrator else "Offline",
                    "SQLite Brain DB": "Online" if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "brain.db")) else "Missing",
                }
                comp_status = "\n".join([f"   - {k}: {v}" for k, v in components.items()])

                plugin_names = [p.__class__.__name__ for p in self.plugins] if self.plugins else []
                plugin_status = ", ".join(plugin_names) if plugin_names else "None detected"

                registered_tools = []
                for tool_name in ["web_search", "browser_search"]:
                    try:
                        if self.tool_registry.get(tool_name):
                            registered_tools.append(tool_name)
                    except:
                        pass
                tool_status = ", ".join(registered_tools) if registered_tools else "None active"

                keys = {
                    "GROQ_API_KEY": "Loaded" if os.getenv("GROQ_API_KEY") else "Missing",
                    "TAVILY_API_KEY": "Loaded" if os.getenv("TAVILY_API_KEY") else "Missing",
                    "OPENROUTER_API_KEY": "Loaded" if os.getenv("OPENROUTER_API_KEY") else "Missing",
                    "SERPER_API_KEY": "Loaded" if os.getenv("SERPER_API_KEY") else "Missing",
                    "SERPAPI_API_KEY": "Loaded" if os.getenv("SERPAPI_API_KEY") else "Missing",
                    "GOOGLE_API_KEY": "Loaded" if os.getenv("GOOGLE_API_KEY") else "Missing",
                    "GOOGLE_CSE_ID": "Loaded" if os.getenv("GOOGLE_CSE_ID") else "Missing",
                    "MOONSHOT_API_KEY": "Loaded" if os.getenv("MOONSHOT_API_KEY") else "Missing",
                }
                key_status = "\n".join([f"   - {k}: {v}" for k, v in keys.items()])

                panel = (
                    f"============ NEO FULL SYSTEM DIAGNOSIS ============\n\n"
                    f"[Core Engine Status]\n"
                    f"   - Active LLM Status: {llm_status}\n"
                    f"   - Autonomous Loop Execution: {'ACTIVE' if self.running else 'IDLE'}\n"
                    f"   - Memory Pipeline Depth: {len(self.conversation)} / {self.max_context} frames\n"
                    f"   - Awaiting Feedback Flag: {self.awaiting_correction}\n\n"
                    f"[Sub-Component Integrity]\n"
                    f"{comp_status}\n\n"
                    f"[Loaded Plugins ({len(self.plugins)})]\n"
                    f"   - {plugin_status}\n\n"
                    f"[Active Tool Registry]\n"
                    f"   - {tool_status}\n\n"
                    f"[API Credential Scope]\n"
                    f"{key_status}\n\n"
                    f"======================================================"
                )
                print("[DEBUG] Panel built successfully.")
                return panel

            print(f"[DEBUG] No command matched for: '{t}'")
            return None

        except Exception as e:
            print(f"[DEBUG] EXCEPTION in handle_commands: {e}")
            traceback.print_exc()
            return f"Command handler error: {e}"

    # =====================================================================
    # MAIN RESPONSE PIPELINE
    # =====================================================================

    def respond(self, text):
        clean_text = text.strip()
        if not clean_text:
            return "Ask something."

        cmd = self.handle_commands(clean_text)
        if cmd:
            return cmd

        fb = self.handle_feedback(clean_text)
        if fb:
            return fb

        if clean_text.startswith("http://") or clean_text.startswith("https://"):
            return self.learn_from_url(clean_text)

        # Check for agent mode signal
        if clean_text.startswith("__AGENT_MODE__:"):
            agent_query = clean_text[15:].strip()
            if self.orchestrator:
                # --- FIXED: Safe async invocation from either a sync context
                # (launcher CLI / Flask) or an already-running event loop
                # (NeoBrainWrapper.respond is async). The original code used a
                # bare asyncio.run(), which raises
                # "RuntimeError: asyncio.run() cannot be called from a running
                # event loop" when called from within an async caller.
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Already inside a running loop — offload to a worker thread.
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            return pool.submit(
                                lambda: asyncio.run(
                                    self.orchestrator.run(agent_query, self.conversation)
                                )
                            ).result()
                    return loop.run_until_complete(
                        self.orchestrator.run(agent_query, self.conversation)
                    )
                except RuntimeError:
                    return asyncio.run(
                        self.orchestrator.run(agent_query, self.conversation)
                    )
                # --- end FIXED ---
            return "Agent orchestrator not initialized."

        clean_text = self.autocorrect(clean_text)

        # NEW: Use reasoning router if available
        if self.reasoning_router:
            try:
                routed = self.reasoning_router.generate(
                    query=clean_text,
                    system_prompt="You are Neo, a precise AI assistant with deep reasoning capabilities.",
                    context=str(self.conversation[-3:]) if self.conversation else "",
                    force_cloud=False
                )
                best = routed["text"]
                model_used = routed["model"]
                reasoning = routed.get("reasoning")
                tier = routed["tier"]

                if reasoning:
                    print(f"[DeepSeek Thinking] {reasoning[:200]}...")
            except Exception as e:
                print(f"[FundiBrain] ReasoningRouter error: {e}. Falling back to legacy.")
                best, model_used, reasoning, tier = self._legacy_pipeline(clean_text)
        else:
            best, model_used, reasoning, tier = self._legacy_pipeline(clean_text)

        best = self.clean(best)

        # Store in memory
        if (
            len(best) > 12
            and "i don't know" not in best.lower()
            and "cannot verify" not in best.lower()
            and "error" not in best.lower()
        ):
            try:
                self.embedder.store(clean_text, best)
                remember(clean_text, best, source="conversation")
            except Exception as e:
                print("[MEMORY ERROR]", e)

        # NEW: Store in unified memory + queue critique
        if self.memory:
            try:
                self.memory.store(clean_text, best, meta={"model": model_used, "tier": tier})
            except Exception as e:
                print(f"[UnifiedMemory] Store error: {e}")

        if self.critique:
            try:
                self.critique.queue_critique(clean_text, best, model_used, reasoning)
            except Exception as e:
                print(f"[Critique] Queue error: {e}")

        self.update_conversation(clean_text, best)
        self.last_question = clean_text
        self.last_answer = best

        # Build response with model attribution
        tier_emoji = {
            "deepseek/deepseek-r1:free": "🧠",
            "qwen/qwen3-235b-a22b:free": "💻",
            "meta-llama/llama-4-maverick:free": "📚",
            "meta-llama/llama-3.3-70b-instruct:free": "⚡",
            "llama-3.3-70b-versatile": "⚡",
            "deepseek/deepseek-chat-v3-0324:free": "💬",
            "openai/gpt-oss-20b:free": "🚀",
            "qwen2.5:1.5b": "💨",
            "deepseek/deepseek-r1:free + tavily": "🔍",
        }
        emoji = tier_emoji.get(model_used, "🤖")

        source_note = ""
        if tier == "research":
            source_note = "\nSources: Tavily web search"
        elif tier == "deep" and reasoning:
            source_note = "\nReasoning: Chain-of-thought visible in console"

        return f"{best}{source_note}\n\n{emoji} [{model_used} | {tier}]\n\nWas this correct? (yes/no)"

    def _legacy_pipeline(self, query):
        """Fallback pipeline when ReasoningRouter is unavailable."""
        candidates = self.collect_evidence(query)
        best = self.verifier.verify(candidates) or "I don't know."
        return best, "legacy", None, "legacy"

    def learn_from_url(self, url):
        print(f"[Neo] Learning URL: {url}")
        try:
            result = search_web(url)
            if not result:
                return "Failed to extract content."

            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass

            if isinstance(result, dict):
                text = result.get("text", str(result))
            else:
                text = str(result)

            if len(text) < 100:
                return "Not enough useful content."

            chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
            stored = 0

            for i, chunk in enumerate(chunks):
                remember(
                    input_text=f"{url} [chunk {i}]",
                    response=chunk,
                    source="url_training",
                    meta={"url": url, "verified": True}
                )
                self.embedder.store(f"{url} chunk {i}", chunk)
                stored += 1

            return f"Learned {stored} chunks from URL."
        except Exception as e:
            return f"URL training failed: {e}"

    # =====================================================================
    # EVIDENCE ENGINE (legacy)
    # =====================================================================

    def collect_evidence(self, query):
        results = []
        query_lower = query.lower()

        try:
            memories = search_knowledge(query)
            for m in memories:
                if not m:
                    continue
                if isinstance(m, str):
                    try:
                        m = json.loads(m)
                    except json.JSONDecodeError:
                        pass
                if isinstance(m, dict):
                    response = m.get("response")
                    memory_input = str(m.get("input_text", "")).lower()
                else:
                    response = str(m)
                    memory_input = ""
                if not response:
                    continue
                if "uganda" in query_lower and "tanzania" in memory_input:
                    continue
                if "tanzania" in query_lower and "uganda" in memory_input:
                    continue
                results.append(("memory", response, 0.90))
        except Exception as e:
            print("[MEMORY ERROR]", e)

        try:
            semantic = self.embedder.search(query)
            for s in semantic:
                if s:
                    results.append(("semantic", str(s), 0.85))
        except Exception as e:
            print("[SEMANTIC ERROR]", e)

        try:
            tool_results = self.run_tools(query)
            for t in tool_results:
                if t:
                    results.append(("tool", str(t), 0.80))
        except Exception as e:
            print("[TOOL ERROR]", e)

        try:
            web = search_web(query)
            if web:
                if isinstance(web, str):
                    try:
                        web = json.loads(web)
                    except json.JSONDecodeError:
                        pass
                if isinstance(web, dict):
                    text = web.get("text", web.get("snippet", str(web)))
                elif isinstance(web, list):
                    text = " ".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in web])
                else:
                    text = str(web)
                if text.strip():
                    results.append(("web", text.strip(), 0.95))
        except Exception as e:
            print("[WEB ERROR]", e)

        if self.mini_llm:
            try:
                llm = self.reason(query)
                if llm:
                    results.append(("llm", llm, 0.70))
            except Exception as e:
                print("[LLM ERROR]", e)

        try:
            if self.kimi and self.kimi.available:
                has_llm = any(src == "llm" for src, _, _ in results)
                if not has_llm:
                    kimi_prompt = (
                        f"You are a precise research assistant. Answer factually and briefly.\n\n"
                        f"Question: {query}\n\nAnswer:"
                    )
                    kimi_result = self.kimi.generate(kimi_prompt, max_tokens=1024, temperature=0.2)
                    if kimi_result:
                        results.append(("kimi", kimi_result, 0.96))
        except Exception as e:
            print("[KIMI ERROR]", e)

        return results

    def _register_tools(self):
        try:
            self.tool_registry.register("web_search", search_web)
        except Exception as e:
            print("[TOOL REGISTER ERROR]", e)
        try:
            self.tool_registry.register("browser_search", self.browser.search_and_extract)
        except Exception as e:
            print("[BROWSER TOOL ERROR]", e)

    def run_tools(self, query):
        results = []
        try:
            tools = self.tool_selector.select_tools(query)
            if not tools:
                return results
            graph = ExecutionGraph()
            for tool_name in tools:
                func = self.tool_registry.get(tool_name)
                if not func:
                    continue
                graph.add_node(tool_name, lambda q=query, f=func: f(q))
            outputs = graph.run()
            for value in outputs.values():
                if not value:
                    continue
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                if isinstance(value, dict):
                    text = value.get("text")
                    if text:
                        results.append(text)
                    else:
                        results.append(str(value))
                else:
                    results.append(str(value))
        except Exception as e:
            print("[TOOL EXECUTION ERROR]", e)
        return results

    def reason(self, query):
        if not self.mini_llm:
            return None
        prompt = f"\nAnswer factually and briefly.\n\nQuestion:\n{query}\n\nAnswer:\n"
        try:
            response = self.mini_llm.generate(prompt)
            if not response:
                return None
            response = re.sub(r'[^\x00-\x7F]+', ' ', response)
            return response[:2000].strip()
        except Exception as e:
            print("[LLM ERROR]", e)
            return None

    # =====================================================================
    # AUTONOMOUS AGENT LOOPS
    # =====================================================================

    def start_autonomous(self):
        if self.running:
            return
        self.running = True
        self.background_thread = threading.Thread(target=self._loop, daemon=True)
        self.background_thread.start()

    def stop_autonomous(self):
        self.running = False

    def _loop(self):
        print("[Neo] Autonomous loop running...")
        while self.running:
            try:
                goal = self.goal_manager.get_next_goal()
                if not goal:
                    time.sleep(2)
                    continue
                print(f"[Goal] {goal}")
                plan = self.planner.create_plan(goal)
                for step in plan:
                    print(f"[Step] {step}")
                    evidence = self.collect_evidence(step)
                    best = self.verifier.verify(evidence)
                    if best:
                        print(f"[Result] {best[:120]}")
                        self.embedder.store(step, best)
                self.goal_manager.complete_goal(goal)
            except Exception as e:
                print("[AUTO ERROR]", e)
            time.sleep(1)

    # =====================================================================
    # FEEDBACK LOOPS
    # =====================================================================

    def handle_feedback(self, text):
        t = text.lower().strip()
        if not self.last_question:
            return None
        if t in ["yes", "correct"]:
            try:
                reinforce(self.last_question, self.last_answer)
            except Exception as e:
                print("[REINFORCE ERROR]", e)
            self.last_question = None
            self.last_answer = None
            return "Reinforced."
        if t in ["no", "wrong", "incorrect"]:
            self.awaiting_correction = True
            return "What is correct?"
        if self.awaiting_correction:
            try:
                penalize(self.last_question, self.last_answer)
                store_correction(self.last_question, text)
                remember(
                    self.last_question,
                    text,
                    source="human_correction",
                    meta={"verified": True}
                )
            except Exception as e:
                print("[CORRECTION ERROR]", e)
            self.awaiting_correction = False
            self.last_question = None
            self.last_answer = None
            return "Correction stored."
        self.last_question = None
        self.last_answer = None
        return None

    # =====================================================================
    # UTILITIES
    # =====================================================================

    def update_conversation(self, u, a):
        self.conversation.append({"user": u, "assistant": a})
        if len(self.conversation) > self.max_context:
            self.conversation.pop(0)
        try:
            conn = _get_db_conn()
            c = conn.cursor()
            c.execute("INSERT INTO conversations (user_input, assistant_response) VALUES (?, ?)", (u, a))
            conn.commit()
            conn.close()
        except Exception as e:
            print("[DB PERSIST ERROR]", e)

    def autocorrect(self, text):
        words = text.split()
        corrected = []
        for w in words:
            matches = get_close_matches(
                w.lower(),
                self.vocab,
                n=1,
                cutoff=0.75
            )
            if matches:
                corrected.append(matches[0])
            else:
                corrected.append(w)
        return " ".join(corrected)

    def clean(self, text):
        text = str(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().capitalize()

    def _build_vocab(self):
        return [
            "who", "what", "where", "when", "why", "how",
            "search", "open", "browser", "goal", "president",
            "uganda", "tanzania", "america", "donald", "trump",
            "museveni", "samia", "kenya", "news", "debug",
            "context", "start", "stop", "auto", "train", "voice",
            "github", "notify", "vision", "agent", "research",
            "scan", "stats", "models", "memory"
        ]

    # =====================================================================
    # NEW: Stats getter for launcher integration
    # =====================================================================
    def show_context(self):
        """Return conversation history."""
        return str(self.conversation) if self.conversation else "(empty)"

    def clear_context(self):
        """Clear conversation history."""
        self.conversation = []
        return "Context cleared."

    def list_goals(self):
        """Return current goals."""
        return getattr(self.goal_manager, "goals", []) or []

    def add_goal(self, task):
        """Add a goal."""
        self.goal_manager.add_goal(task)
        return f"Goal added: {task}"

    def get_stats(self):
        """Return system stats for launcher display."""
        return {
            "tool_independence": 0.0,
            "total_calls": len(self.conversation),
            "agent_calls": 0,
            "cognitive_only_calls": len(self.conversation),
            "tool_assisted_calls": 0,
        }