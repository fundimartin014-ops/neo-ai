"""
core/orchestrator.py
THE BRAIN STEM — ReAct agent loop with LLMRouter + Tavily research.
All heavy thinking goes to free cloud models. Zero local RAM strain.
"""

import json
import re
import asyncio
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

# Optional ReasoningRouter — falls back to direct LLMRouter if unavailable
try:
    from core.meta_cognition import ReasoningRouter, ReasoningTier
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False
    ReasoningRouter = None
    ReasoningTier = None

# Optional NeoToolPlugin — pre-flight "no-signup" tool layer
try:
    from neo_nosignups import NeoToolPlugin
    NEO_TOOL_PLUGIN_AVAILABLE = True
except ImportError:
    NEO_TOOL_PLUGIN_AVAILABLE = False
    NeoToolPlugin = None

# Optional SystemScanner — used as self.scanner in __init__
try:
    from core.system_scanner import SystemScanner
    SYSTEM_SCANNER_AVAILABLE = True
except ImportError:
    try:
        from system_scanner import SystemScanner  # type: ignore
        SYSTEM_SCANNER_AVAILABLE = True
    except ImportError:
        SYSTEM_SCANNER_AVAILABLE = False
        SystemScanner = None

from core.tavily_search import tavily_search


class AgentState(Enum):
    THINKING = "thinking"
    RESEARCHING = "researching"
    ACTING = "acting"
    OBSERVING = "observing"
    RESPONDING = "responding"
    COMPLETE = "complete"


@dataclass
class ToolCall:
    tool: str
    parameters: Dict[str, Any]
    reasoning: str


class NeoOrchestrator:
    """
    ReAct coordinator with deep reasoning and web research.
    Uses LLMRouter directly for generation with ReasoningRouter as optional enhancer.
    """

    def __init__(self, llm_router, plugins: Dict, memory_systems=None, max_iterations: int = 5):
        self.llm = llm_router
        self.plugins = plugins
        self.memory = memory_systems
        self.max_iterations = max_iterations
        self.tools = self._build_tool_catalog()
        self.conversation_history: List[Dict] = []
        self.execution_log: List[Dict] = []

        self.scanner = SystemScanner() if SYSTEM_SCANNER_AVAILABLE else None

        self.neo_tools = None
        self.last_tool_data: Optional[Dict] = None
        if NEO_TOOL_PLUGIN_AVAILABLE:
            try:
                self.neo_tools = NeoToolPlugin("tools.json")
                print("[Orchestrator] NeoToolPlugin loaded (pre-flight intent layer).")
            except Exception as e:
                print(f"[Orchestrator] NeoToolPlugin init failed: {e}")
                self.neo_tools = None

        self.router = None
        if REASONING_AVAILABLE and llm_router:
            try:
                self.router = ReasoningRouter(llm_router)
                print("[Orchestrator] ReasoningRouter loaded.")
            except Exception as e:
                print(f"[Orchestrator] ReasoningRouter init failed: {e}. Using direct LLMRouter.")

    def _build_tool_catalog(self) -> List[Dict]:
        catalog = []
        tool_map = {
            "web_trainer": {
                "name": "web_search",
                "description": "Search the web for current information, news, or facts.",
                "parameters": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "default": 3}
                }
            },
            "database_plugin": {
                "name": "memory_search",
                "description": "Search Neo's vector memory for stored documents and past conversations.",
                "parameters": {
                    "query": {"type": "string", "description": "What to search for"},
                    "top_k": {"type": "integer", "default": 5}
                }
            },
            "github_plugin": {
                "name": "github_search",
                "description": "Search GitHub repositories for code, libraries, or projects.",
                "parameters": {
                    "query": {"type": "string", "description": "Search query"},
                    "language": {"type": "string", "optional": True}
                }
            },
            "pdf_answer_plugin": {
                "name": "pdf_query",
                "description": "Query trained PDF documents for specific information.",
                "parameters": {
                    "question": {"type": "string", "description": "Question about PDF content"}
                }
            },
            "calendar_plugin": {
                "name": "calendar",
                "description": "Check or manage calendar events and schedules.",
                "parameters": {
                    "action": {"type": "string", "enum": ["check", "add", "list", "delete"]},
                    "date": {"type": "string", "optional": True},
                    "description": {"type": "string", "optional": True}
                }
            },
            "vision_plugin": {
                "name": "vision_analyze",
                "description": "Analyze images using vision models (Moondream via Ollama).",
                "parameters": {
                    "image_path": {"type": "string", "description": "Path to image"},
                    "prompt": {"type": "string", "default": "Describe what you see"}
                }
            },
            "notification_plugin": {
                "name": "send_notification",
                "description": "Send alerts via ntfy.sh or Discord webhook.",
                "parameters": {
                    "message": {"type": "string", "description": "Notification message"},
                    "channel": {"type": "string", "enum": ["ntfy", "discord"], "default": "ntfy"}
                }
            },
            "email_plugin": {
                "name": "send_email",
                "description": "Send email messages.",
                "parameters": {
                    "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}
                }
            },
            "spreadsheet_plugin": {
                "name": "spreadsheet",
                "description": "Create or modify spreadsheets.",
                "parameters": {
                    "action": {"type": "string", "enum": ["create", "read", "write", "export"]},
                    "data": {"type": "array", "optional": True},
                    "filename": {"type": "string", "optional": True}
                }
            },
            "scheduler_plugin": {
                "name": "schedule_task",
                "description": "Schedule automated tasks or reminders.",
                "parameters": {
                    "task": {"type": "string", "description": "Task description"},
                    "schedule": {"type": "string", "description": "When to run"}
                }
            },
            "http_plugin": {
                "name": "http_request",
                "description": "Make HTTP GET/POST requests to APIs.",
                "parameters": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                    "url": {"type": "string"}, "body": {"type": "object", "optional": True},
                    "headers": {"type": "object", "optional": True}
                }
            },
            "cache_plugin": {
                "name": "cache_lookup",
                "description": "Check cached results for recent queries.",
                "parameters": {
                    "key": {"type": "string", "description": "Cache key"}
                }
            },
            "analytics_plugin": {
                "name": "analytics",
                "description": "Get system analytics and usage statistics.",
                "parameters": {
                    "metric": {"type": "string", "enum": ["usage", "performance", "errors", "plugins"]}
                }
            },
            "monitor_plugin": {
                "name": "system_monitor",
                "description": "Monitor system health and resources.",
                "parameters": {
                    "check": {"type": "string", "enum": ["cpu", "memory", "disk", "network", "all"], "default": "all"}
                }
            },
            "log_plugin": {
                "name": "read_logs",
                "description": "Read system logs.",
                "parameters": {
                    "lines": {"type": "integer", "default": 50},
                    "level": {"type": "string", "enum": ["INFO", "ERROR", "DEBUG", "WARNING"], "optional": True}
                }
            },
            "alert_plugin": {
                "name": "trigger_alert",
                "description": "Trigger system alerts.",
                "parameters": {
                    "type": {"type": "string"}, "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"], "default": "medium"}
                }
            },
            "progress_plugin": {
                "name": "track_progress",
                "description": "Track task progress.",
                "parameters": {
                    "task": {"type": "string"}, "status": {"type": "string", "enum": ["start", "update", "complete", "pause"]},
                    "note": {"type": "string", "optional": True}
                }
            },
            "trainer_plugin": {
                "name": "train_model",
                "description": "Train on new text data.",
                "parameters": {
                    "text": {"type": "string"}, "category": {"type": "string", "default": "general"},
                    "source": {"type": "string", "default": "user"}
                }
            },
            "voice_trainer_plugin": {
                "name": "voice_train",
                "description": "Train voice recognition models.",
                "parameters": {
                    "audio_samples": {"type": "array"}, "label": {"type": "string"}
                }
            },
            "system_scanner": {
                "name": "system_scan",
                "description": "Run system capability scan (RAM, models, API keys, GPU).",
                "parameters": {
                    "quick": {"type": "boolean", "default": False, "description": "Quick scan vs full scan"}
                }
            }
        }

        def normalize(name):
            name = unicodedata.normalize("NFKC", name).lower()
            name = re.sub(r"\s*\(\d+\)$", "", name)
            return re.sub(r"[^a-z0-9]", "", name.replace("_plugin", "").replace("_trainer", ""))

        for plugin_name, definition in tool_map.items():
            norm_plugin = normalize(plugin_name)
            for key in self.plugins.keys():
                norm_key = normalize(key)
                if norm_plugin == norm_key or norm_plugin in norm_key or norm_key in norm_plugin:
                    catalog.append(definition)
                    break

        return catalog

    def _build_system_prompt(self) -> str:
        """
        Build the ReAct system prompt.

        FIXED: With ~99 tools registered (19 curated + ~80 lazy), dumping the
        whole catalog as JSON pushed the prompt to ~15,000 tokens and Groq
        rejected it with HTTP 413 (Payload Too Large). We now:

          - Include the first N=19 curated tools with their full parameter
            schema (they're the ones with structured args the LLM needs to
            know about).
          - Include every other tool as a COMPACT NAME-ONLY list so the LLM
            still knows what's available and can call it by name. The
            executor looks up by name in self.plugins, so parameters don't
            need to be enumerated for the lazy ones.

        Prompt size drops back to ~3,500 tokens. Nothing becomes unreachable.
        """
        import datetime

        # 19 curated tools (the ones from _build_tool_catalog) with full schema
        curated_count = 19
        curated_tools = self.tools[:curated_count]
        other_tools = self.tools[curated_count:]

        tools_json = json.dumps(curated_tools, indent=2)

        # Compact name list for everything else
        other_names = [t.get("name", "") for t in other_tools if t.get("name")]
        # Filter out empties and cap at 80 to keep prompt bounded
        other_names = [n for n in other_names if n][:80]
        if other_names:
            other_section = (
                "## ADDITIONAL TOOLS (call by name with "
                '{"action": "<name>", "parameters": {...}})\n'
                + ", ".join(other_names)
            )
        else:
            other_section = ""

        json_template_lines = [
            "{",
            '    "thought": "Your step-by-step reasoning about what to do",',
            '    "action": "tool_name",',
            '    "parameters": { ... }',
            "}",
        ]
        json_template = "\n".join(json_template_lines)

        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        prompt_parts = [
            "You are Neo, an autonomous AI agent. You have access to tools.",
            "",
            "## CORE TOOLS (with parameter schema)",
            tools_json,
            "",
        ]
        if other_section:
            prompt_parts.append(other_section)
            prompt_parts.append("")

        prompt_parts.extend([
            "## RULES",
            "1. Analyze the user's request carefully",
            "2. If you need tool data, respond ONLY with a JSON block:",
            json_template,
            "3. After receiving tool results, continue reasoning or provide final answer",
            "4. You may chain multiple tools (up to " + str(self.max_iterations) + " steps)",
            "5. Be concise and accurate. Do not hallucinate tool names.",
            "6. PREFER TOOLS. If any listed tool's name or description matches"
            " the user's intent, output the JSON tool call. Do NOT try to"
            " answer from memory when a tool applies.",
            "7. Compute, convert, reverse, uppercase, random, uuid, fibonacci,"
            " date, json, regex, and math operations ALWAYS have a matching"
            " tool. Use it instead of answering.",
            "",
            "## RESPONSE FORMAT",
            "- Need tool: output JSON block above",
            "- Have enough info: respond directly to user",
            "- Final answer should synthesize all tool results",
            "",
            "## CONTEXT",
            "User: Fundi (building Neo as personal AI system)",
            "Current date: " + current_date,
            "Mode: Agent orchestration with ReAct loop",
            "",
        ])
        return "\n".join(prompt_parts)

    async def _generate(self, prompt: str, system_prompt: str, task_type: str = "general",
                        prefer_openrouter: bool = False) -> Dict:
        """
        Unified generation with LLMRouter + fallback chain.
        Tries: LLMRouter → ReasoningRouter → LocalLLM engine → error
        """
        if self.llm and hasattr(self.llm, 'generate'):
            try:
                result = await self.llm.generate(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    task_type=task_type,
                    prefer_openrouter=prefer_openrouter,
                    temperature=0.3,
                    max_tokens=2048,
                    retries=1
                )
                if result and not result.startswith("[Error]") and len(result) >= 3:
                    return {
                        "text": result,
                        "model": getattr(self.llm, '_select_model', lambda *a, **k: 'unknown')(task_type),
                        "tier": task_type,
                        "reasoning": None
                    }
            except Exception as e:
                print(f"[Orchestrator] LLMRouter error: {e}")

        if self.router:
            try:
                return self.router.generate(
                    query=prompt,
                    system_prompt=system_prompt,
                    force_cloud=True
                )
            except Exception as e:
                print(f"[Orchestrator] ReasoningRouter error: {e}")

        if self.llm and hasattr(self.llm, 'engine') and self.llm.engine:
            try:
                result = self.llm.engine.generate(prompt, system=system_prompt)
                if result and len(result) >= 3:
                    return {
                        "text": result,
                        "model": "local_llm_fallback",
                        "tier": "fallback",
                        "reasoning": None
                    }
            except Exception as e:
                print(f"[Orchestrator] Engine fallback error: {e}")

        return {
            "text": "[Error] All generation engines failed. Check API keys and connectivity.",
            "model": "error",
            "tier": "error",
            "reasoning": None
        }

    async def run(self, user_input: str, conversation_history: List[Dict] = None) -> str:
        if self.neo_tools:
            try:
                tool_result = self.neo_tools.handle_intent(user_input)
                if tool_result and tool_result.get("has_tool"):
                    self.execution_log.append({
                        "iteration": 0,
                        "state": "neo_tool_short_circuit",
                        "input": user_input,
                        "tools": tool_result.get("tools"),
                    })
                    self.last_tool_data = {
                        "has_tool": True,
                        "tools": tool_result.get("tools"),
                        "iframe_html": tool_result.get("iframe_html"),
                    }
                    return tool_result.get("response_text", "[Tool executed]")
            except Exception as e:
                print(f"[Orchestrator] NeoToolPlugin pre-flight error: {e}")

        state = AgentState.THINKING
        context = self._build_context(user_input, conversation_history)
        tool_results = []
        research_results = []
        iteration = 0
        current_call = None

        memory_context = ""
        if self.memory:
            try:
                mem_results = self.memory.query(user_input, top_k=3)
                memory_context = mem_results.get("summary", "")
            except Exception as e:
                print(f"[Orchestrator] Memory query error: {e}")

        full_context = context + "\n\n## RELEVANT MEMORY\n" + memory_context + "\n"

        while iteration < self.max_iterations and state != AgentState.RESPONDING:
            iteration += 1

            if state == AgentState.THINKING:
                tool_results_text = json.dumps(tool_results, indent=2) if tool_results else "None yet"
                research_text = json.dumps(research_results, indent=2) if research_results else "None yet"

                think_prompt = (
                    full_context +
                    "\n\n## TOOL RESULTS SO FAR\n" + tool_results_text +
                    "\n\n## WEB RESEARCH SO FAR\n" + research_text +
                    "\n\nDecide: Do you need a tool? Do you need web research? "
                    "Output JSON if you need a tool, 'RESEARCH: <query>' if you need web search, "
                    "or plain text if you can answer directly."
                )

                routed = await self._generate(
                    prompt=think_prompt,
                    system_prompt=self._build_system_prompt(),
                    task_type="agent_orchestration"
                )

                response = routed["text"]
                model_used = routed["model"]
                print(f"[Orchestrator] Thinking via {model_used} (tier: {routed['tier']})")

                if response.strip().upper().startswith("RESEARCH:"):
                    research_query = response.split(":", 1)[1].strip()
                    state = AgentState.RESEARCHING
                    current_call = ToolCall(
                        tool="web_research",
                        parameters={"query": research_query},
                        reasoning=f"Agent requested web research: {research_query}"
                    )
                    self.execution_log.append({
                        "iteration": iteration,
                        "state": "researching",
                        "query": research_query,
                        "model": model_used
                    })
                    continue

                if self._is_tool_call(response):
                    current_call = self._parse_tool_call(response)
                    self.execution_log.append({
                        "iteration": iteration,
                        "state": "thinking",
                        "thought": current_call.reasoning,
                        "action": current_call.tool,
                        "model": model_used
                    })
                    state = AgentState.ACTING
                else:
                    self.execution_log.append({
                        "iteration": iteration,
                        "state": "responding_direct",
                        "response": response,
                        "model": model_used
                    })
                    return response

            elif state == AgentState.RESEARCHING:
                research_query = current_call.parameters.get("query", "")
                print(f"[Orchestrator] Researching: {research_query}")

                try:
                    tavily_result = tavily_search(
                        query=research_query,
                        search_depth="basic",
                        max_results=5,
                        include_answer=True
                    )
                    research_results.append({
                        "query": research_query,
                        "result": tavily_result[:2000] if tavily_result else "No results found"
                    })
                    self.execution_log.append({
                        "iteration": iteration,
                        "state": "research_complete",
                        "query": research_query,
                        "result_preview": str(tavily_result)[:200] if tavily_result else "None"
                    })
                except Exception as e:
                    print(f"[Orchestrator] Tavily search error: {e}")
                    research_results.append({"query": research_query, "result": f"[Error] {e}"})

                state = AgentState.THINKING

            elif state == AgentState.ACTING:
                result = await self._execute_tool(current_call)
                tool_results.append({
                    "tool": current_call.tool,
                    "parameters": current_call.parameters,
                    "result": str(result)[:1000]
                })
                self.execution_log.append({
                    "iteration": iteration,
                    "state": "acting",
                    "tool": current_call.tool,
                    "result_preview": str(result)[:200]
                })
                state = AgentState.OBSERVING

            elif state == AgentState.OBSERVING:
                state = AgentState.THINKING

        final_prompt = (
            full_context +
            "\n\n## ALL TOOL RESULTS\n" + json.dumps(tool_results, indent=2) +
            "\n\n## ALL WEB RESEARCH\n" + json.dumps(research_results, indent=2) +
            "\n\nProvide a final answer synthesizing ALL information. Be concise and cite sources implicitly."
        )

        final_routed = await self._generate(
            prompt=final_prompt,
            system_prompt=self._build_system_prompt(),
            task_type="general"
        )

        final_answer = final_routed["text"]
        self.execution_log.append({
            "iteration": iteration,
            "state": "complete",
            "response": final_answer,
            "model": final_routed["model"]
        })
        return final_answer

    def chat(self, user_input: str):
        if self.neo_tools:
            try:
                tool_result = self.neo_tools.handle_intent(user_input)
                if tool_result and tool_result.get("has_tool"):
                    self.execution_log.append({
                        "iteration": 0,
                        "state": "neo_tool_short_circuit_chat",
                        "input": user_input,
                        "tools": tool_result.get("tools"),
                    })
                    return {
                        "role": "ai",
                        "content": tool_result.get("response_text", "[Tool executed]"),
                        "tool_data": {
                            "has_tool": True,
                            "tools": tool_result.get("tools"),
                            "iframe_html": tool_result.get("iframe_html"),
                        }
                    }
            except Exception as e:
                print(f"[Orchestrator] NeoToolPlugin pre-flight error (chat): {e}")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    answer = pool.submit(lambda: asyncio.run(self.run(user_input))).result()
            else:
                answer = loop.run_until_complete(self.run(user_input))
        except RuntimeError:
            answer = asyncio.run(self.run(user_input))

        tool_data = self.last_tool_data
        self.last_tool_data = None

        if tool_data and tool_data.get("has_tool"):
            return {
                "role": "ai",
                "content": answer,
                "tool_data": tool_data
            }
        return {"role": "ai", "content": answer}

    def _is_tool_call(self, response: str) -> bool:
        return '"action"' in response and '"parameters"' in response and '"thought"' in response

    def _parse_tool_call(self, response: str) -> ToolCall:
        json_str = response.strip()
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        try:
            data = json.loads(json_str.strip())
            return ToolCall(
                tool=data.get("action", ""),
                parameters=data.get("parameters", {}),
                reasoning=data.get("thought", "No reasoning provided")
            )
        except json.JSONDecodeError as e:
            print(f"[Orchestrator] JSON parse error: {e}")
            action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response)
            if action_match:
                return ToolCall(
                    tool=action_match.group(1),
                    parameters={},
                    reasoning="Failed to parse full JSON, using regex fallback"
                )
            raise ValueError(f"Cannot parse tool call: {response[:200]}")

    async def _execute_tool(self, call: ToolCall) -> str:
        tool_to_plugin = {
            "web_search": ["web_trainer", "webtrainer", "web_trainer_plugin"],
            "memory_search": ["database_plugin", "database", "databaseplugin"],
            "github_search": ["github_plugin", "github", "githubplugin"],
            "pdf_query": ["pdf_answer_plugin", "pdfanswer", "pdf_trainer", "pdf_trainer_plugin"],
            "calendar": ["calendar_plugin", "calendar", "calendarplugin"],
            "vision_analyze": ["vision_plugin", "vision", "visionplugin"],
            "voice_transcribe": ["voice_plugin", "voice", "voiceplugin"],
            "send_notification": ["notification_plugin", "notification", "notificationplugin"],
            "send_email": ["email_plugin", "email", "emailplugin"],
            "spreadsheet": ["spreadsheet_plugin", "spreadsheet", "spreadsheetplugin"],
            "schedule_task": ["scheduler_plugin", "scheduler", "schedulerplugin"],
            "http_request": ["http_plugin", "http", "httpplugin"],
            "cache_lookup": ["cache_plugin", "cache", "cacheplugin"],
            "analytics": ["analytics_plugin", "analytics", "analyticsplugin"],
            "system_monitor": ["monitor_plugin", "monitor", "monitorplugin"],
            "read_logs": ["log_plugin", "log", "logplugin"],
            "trigger_alert": ["alert_plugin", "alert", "alertplugin"],
            "track_progress": ["progress_plugin", "progress", "progressplugin"],
            "train_model": ["trainer_plugin", "trainer", "trainerplugin"],
            "voice_train": ["voice_trainer_plugin", "voicetrainer", "voice_trainer"],
            "system_scan": ["system_scanner", "scanner", "systemscanner"]
        }

        plugin = None
        possible_keys = tool_to_plugin.get(call.tool, [call.tool])
        for key in possible_keys:
            if key in self.plugins:
                plugin = self.plugins[key]
                break

        if not plugin:
            return f"[Error] Tool '{call.tool}' not available. Available: {list(self.plugins.keys())}"

        try:
            return await self._call_plugin_method(plugin, call.tool, call.parameters)
        except Exception as e:
            return f"[Error] {call.tool} execution failed: {str(e)}"

    async def _call_plugin_method(self, plugin, tool_name: str, params: Dict) -> str:
        method_names = [
            'run', 'execute', 'process', 'handle',
            tool_name.replace('_', ''),
            tool_name.split('_')[0]
        ]
        for method_name in method_names:
            if hasattr(plugin, method_name):
                method = getattr(plugin, method_name)
                if callable(method):
                    try:
                        if asyncio.iscoroutinefunction(method):
                            result = await method(**params)
                        else:
                            result = method(**params)
                        return str(result) if result is not None else "[No output]"
                    except TypeError:
                        continue
        if hasattr(plugin, 'run'):
            try:
                result = plugin.run()
                return str(result) if result is not None else "[Plugin executed]"
            except Exception as e:
                return f"[Error] Fallback run() failed: {e}"
        return f"[Error] No executable method found for {tool_name}"

    def _build_context(self, user_input: str, history: List[Dict] = None) -> str:
        context = f"User request: {user_input}\n"
        if history:
            recent = history[-5:]
            hist_text = "\n".join([
                f"User: {h.get('user', '')}\nAssistant: {h.get('assistant', '')}"
                for h in recent
            ])
            context += f"\nRecent conversation:\n{hist_text}\n"
        return context

    def get_execution_log(self) -> List[Dict]:
        return self.execution_log

    def get_stats(self) -> Dict:
        return {
            "tools_available": len(self.tools),
            "plugins_mapped": len(self.plugins),
            "max_iterations": self.max_iterations,
            "last_execution": self.execution_log[-1] if self.execution_log else None,
            "total_executions": len(self.execution_log),
            "reasoning_router_active": self.router is not None,
            "neo_tool_plugin_active": self.neo_tools is not None,
            "system_scanner_active": self.scanner is not None,
        }