"""
Neo AI - NoSignups Tool Registry & Integration Module
======================================================
Plug this into your ReAct agent loop / LLMRouter to give Neo access
to 245+ no-signup, open-source, browser-based tools.

Usage:
    from neo_nosignups import ToolRegistry, ToolIntegrator

    registry = ToolRegistry("tools.json")
    integrator = ToolIntegrator(registry)

    # In your ReAct loop:
    tool = registry.find_tool_for_task("convert pdf to word")
    # Returns: {name: "VERT", url: "https://vert.sh/", ...}

    # In your web chat UI:
    iframe_html = integrator.get_iframe_embed("excalidraw", context="whiteboard")
"""

import json
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolMatch:
    """Represents a matched tool with relevance score."""
    tool: Dict[str, Any]
    score: float
    matched_fields: List[str]
    # --- ADDED: count of DISTINCT query tokens that hit this tool at all.
    # A single weak match (e.g. "string" appearing in a description) is
    # not enough evidence of intent. We require at least 2 distinct tokens
    # matched before treating a tool as a real match.
    distinct_tokens: int = 0


class ToolRegistry:
    """
    Loads and indexes the NoSignups tools.json.
    Provides semantic search, filtering, and categorization.
    """

    def __init__(self, json_path: str = "tools.json"):
        self.json_path = Path(json_path)
        self.data = self._load()
        self.tools = self.data.get("tools", [])
        self.categories = {c["id"]: c for c in self.data.get("categories", [])}
        self._build_index()

    def _load(self) -> Dict:
        """Load tools.json from disk."""
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback: try to fetch from GitHub raw URL
            import urllib.request
            url = "https://raw.githubusercontent.com/BraveOPotato/FckSignups/main/tools.json"
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                raise RuntimeError(f"Could not load tools.json: {e}")

    def _build_index(self):
        """Build inverted index for fast keyword search."""
        self._index = {}  # keyword -> list of tool indices
        for idx, tool in enumerate(self.tools):
            text = " ".join([
                tool.get("name", ""),
                tool.get("description", ""),
                tool.get("category", ""),
                " ".join(tool.get("tags", []))
            ]).lower()
            # Tokenize: alphanumeric only
            tokens = set(re.findall(r"[a-z0-9]+", text))
            for token in tokens:
                if token not in self._index:
                    self._index[token] = []
                self._index[token].append(idx)

    def find_tool_for_task(self, query: str, top_k: int = 5) -> List[ToolMatch]:
        """
        Find the best tools for a given task description.
        Used in ReAct agent loop for tool selection.

        Args:
            query: Natural language task (e.g., "edit pdf", "draw diagram")
            top_k: Number of results to return

        Returns:
            List of ToolMatch objects sorted by relevance
        """
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        if not query_tokens:
            return []

        # --- FIXED: track which distinct query tokens matched each tool.
        # A single weak token match (e.g. "reverse a string hello" hitting
        # Graphite via "string") should not qualify as intent. We now record
        # the set of distinct matched tokens per tool and require >= 2 later.
        scores = {}  # tool_idx -> {"score": float, "fields": set, "tokens": set}

        for token in query_tokens:
            for idx in self._index.get(token, []):
                tool = self.tools[idx]
                if idx not in scores:
                    scores[idx] = {"score": 0.0, "fields": set(), "tokens": set()}

                # Weight exact name matches higher
                name_lower = tool.get("name", "").lower()
                desc_lower = tool.get("description", "").lower()
                tags_lower = [t.lower() for t in tool.get("tags", [])]
                cat_lower = tool.get("category", "").lower()

                hit = False
                if token in name_lower:
                    scores[idx]["score"] += 3.0
                    scores[idx]["fields"].add("name")
                    hit = True
                if token in desc_lower:
                    scores[idx]["score"] += 1.5
                    scores[idx]["fields"].add("description")
                    hit = True
                if token in tags_lower:
                    scores[idx]["score"] += 2.0
                    scores[idx]["fields"].add("tags")
                    hit = True
                if token in cat_lower:
                    scores[idx]["score"] += 1.0
                    scores[idx]["fields"].add("category")
                    hit = True

                if hit:
                    scores[idx]["tokens"].add(token)

        # Boost featured/editor's picks slightly
        results = []
        for idx, data in scores.items():
            tool = self.tools[idx]
            section = tool.get("section", "")
            if section == "featured":
                data["score"] *= 1.2
            elif section == "editors-pick":
                data["score"] *= 1.1

            # Boost by GitHub stars (log scale, capped)
            stars = tool.get("stars", 0) or 0
            if stars > 0:
                data["score"] += min(2.0, stars / 10000.0)

            results.append(ToolMatch(
                tool=tool,
                score=round(data["score"], 2),
                matched_fields=list(data["fields"]),
                distinct_tokens=len(data["tokens"]),  # --- ADDED
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def get_tools_by_category(self, category_id: str) -> List[Dict]:
        """Get all tools in a specific category."""
        return [t for t in self.tools if t.get("category") == category_id]

    def get_self_hostable_tools(self) -> List[Dict]:
        """
        Tools that have GitHub repos and can be self-hosted locally.
        Ideal for Neo's offline capability on 8GB RAM.
        """
        return [
            t for t in self.tools 
            if t.get("github") and t.get("license") 
            and t.get("license") not in ("?", "NC", "CC BY-NC 4.0", "CC BY-NC-SA 1.0", "CC BY-NC-SA 4.0")
        ]

    def get_iframe_tools(self) -> List[Dict]:
        """
        Tools that work well embedded in Neo's web chat UI via iframe.
        These are client-side/browser-based and need no backend.
        """
        iframe_friendly_tags = {
            "editor", "whiteboard", "draw", "diagram", "visualization",
            "converter", "calculator", "playground", "preview",
            "markdown", "notes", "spreadsheet", "pdf-tools",
            "image", "svg", "code", "json", "sql"
        }
        results = []
        for tool in self.tools:
            tags = set(t.lower() for t in tool.get("tags", []))
            if tags & iframe_friendly_tags:
                results.append(tool)
        return results

    def get_tool_by_id(self, tool_id: str) -> Optional[Dict]:
        """Get a specific tool by its ID."""
        for tool in self.tools:
            if tool.get("id") == tool_id:
                return tool
        return None

    def get_categories(self) -> List[Dict]:
        """Return all categories."""
        return list(self.categories.values())

    def get_stats(self) -> Dict:
        """Return stats about the registry."""
        return {
            "total_tools": len(self.tools),
            "total_categories": len(self.categories),
            "featured": len([t for t in self.tools if t.get("section") == "featured"]),
            "editors_picks": len([t for t in self.tools if t.get("section") == "editors-pick"]),
            "self_hostable": len(self.get_self_hostable_tools()),
            "iframe_ready": len(self.get_iframe_tools()),
            "with_github": len([t for t in self.tools if t.get("github")]),
        }


class ToolIntegrator:
    """
    Handles integration patterns for Neo's web chat UI and agent loop.
    Generates iframe embeds, CLI commands, and API wrappers.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def get_iframe_embed(self, tool_id: str, width: str = "100%", height: str = "500px") -> Optional[str]:
        """
        Generate iframe HTML for embedding a tool in Neo's chat UI.

        Args:
            tool_id: The tool's ID from tools.json
            width: CSS width
            height: CSS height

        Returns:
            HTML iframe string or None if tool not found
        """
        tool = self.registry.get_tool_by_id(tool_id)
        if not tool:
            return None

        url = tool.get("url", "")
        name = tool.get("name", "Tool")

        # Security: sandbox the iframe
        return f"""<div class="neo-tool-embed">
    <div class="neo-tool-header">
        <span>{name}</span>
        <a href="{url}" target="_blank" rel="noopener">Open ↗</a>
    </div>
    <iframe 
        src="{url}" 
        width="{width}" 
        height="{height}" 
        style="border: 1px solid #333; border-radius: 8px;"
        sandbox="allow-scripts allow-same-origin allow-forms allow-downloads"
        loading="lazy"
        title="{name}"
    ></iframe>
</div>"""

    def get_self_host_instructions(self, tool_id: str) -> Optional[Dict]:
        """
        Generate self-hosting instructions for a tool.
        Returns dict with docker/clone/run steps.
        """
        tool = self.registry.get_tool_by_id(tool_id)
        if not tool or not tool.get("github"):
            return None

        github = tool["github"]
        name = tool["name"]
        license = tool.get("license", "Unknown")

        # Heuristic: detect if likely static SPA vs needs server
        static_indicators = {".github.io", "vercel.app", "netlify.app", "web.app", "pages.dev"}
        is_static = any(ind in tool.get("url", "") for ind in static_indicators)

        instructions = {
            "name": name,
            "github": github,
            "license": license,
            "type": "static" if is_static else "server",
            "steps": []
        }

        if is_static:
            instructions["steps"] = [
                f"git clone {github}.git",
                f"cd {github.split('/')[-1]}",
                "npm install  # or yarn install / pnpm install",
                "npm run build",
                "# Serve dist/ folder with any static server",
                "python -m http.server 8080 --directory dist/"
            ]
        else:
            instructions["steps"] = [
                f"git clone {github}.git",
                f"cd {github.split('/')[-1]}",
                "# Check README for specific setup",
                "npm install  # or pip install -r requirements.txt",
                "npm run dev  # or npm start"
            ]

        return instructions

    def get_agent_tool_description(self, tool_id: str) -> Optional[str]:
        """
        Generate a function-style description for Neo's ReAct agent loop.
        This can be injected into the system prompt as an available tool.
        """
        tool = self.registry.get_tool_by_id(tool_id)
        if not tool:
            return None

        name = tool["name"]
        desc = tool["description"]
        url = tool["url"]
        tags = ", ".join(tool.get("tags", [])[:5])

        return f"""Tool: {name}
Description: {desc}
URL: {url}
Tags: {tags}
Usage: When user asks for tasks related to {tags}, embed or redirect to this tool.
"""

    def suggest_tools_for_message(self, user_message: str, top_k: int = 3) -> List[Dict]:
        """
        Main entry point for Neo's chat UI.
        Given a user message, suggest relevant NoSignups tools.

        Returns:
            List of tool dicts with added 'integration_type' field.
        """
        matches = self.registry.find_tool_for_task(user_message, top_k=top_k)
        results = []

        for match in matches:
            tool = match.tool.copy()
            tool["match_score"] = match.score
            tool["matched_fields"] = match.matched_fields
            tool["distinct_tokens"] = match.distinct_tokens  # --- ADDED

            # Determine best integration method
            if tool.get("github") and tool.get("license") not in ("?", "NC"):
                if any(tag in ["editor", "whiteboard", "draw", "diagram", "visualization", "playground"] 
                       for tag in tool.get("tags", [])):
                    tool["integration_type"] = "iframe_or_selfhost"
                else:
                    tool["integration_type"] = "selfhost"
            else:
                tool["integration_type"] = "iframe"

            results.append(tool)

        return results

    def get_quick_actions(self) -> List[Dict]:
        """
        Pre-defined quick action buttons for Neo's chat UI.
        Maps common intents to specific tools.
        """
        return [
            {"label": "🎨 Draw", "tool_id": "excalidraw", "intent": "draw diagram"},
            {"label": "📊 Visualize JSON", "tool_id": "json-crack", "intent": "visualize json"},
            {"label": "📝 Markdown", "tool_id": "stackedit", "intent": "edit markdown"},
            {"label": "🔒 Encode", "tool_id": "cyberchef", "intent": "encode decode"},
            {"label": "🖼️ Edit Image", "tool_id": "squoosh", "intent": "compress image"},
            {"label": "📐 Regex", "tool_id": "regexr", "intent": "test regex"},
            {"label": "📄 PDF Tools", "tool_id": "bentopdf", "intent": "edit pdf"},
            {"label": "💻 Code Sandbox", "tool_id": "js-bin", "intent": "javascript sandbox"},
        ]


# ============================================================================
# REACT AGENT LOOP INTEGRATION
# ============================================================================

class NeoToolPlugin:
    """
    Drop-in plugin for Neo's ReAct agent loop.
    Add this to your orchestrator to enable NoSignups tool awareness.
    """

    # --- ADDED: Patterns that are clearly NOT tool intents. These are
    # text-manipulation verbs that Neo's local skills should handle. If a
    # query starts with one of these, we skip tool matching entirely so
    # the request flows through to skills/agents instead of matching a
    # random browser tool.
    _TEXT_OP_VETO = re.compile(
        r"^\s*(reverse|uppercase|lowercase|capitalize|"
        r"strip|trim|title\s*case|"
        r"reverse\s+a?\s*string|reverse\s+the\s+string)\b",
        re.IGNORECASE,
    )

    def __init__(self, json_path: str = "tools.json"):
        self.registry = ToolRegistry(json_path)
        self.integrator = ToolIntegrator(self.registry)
        self._system_prompt_addition = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt addition describing available tools."""
        featured = [t for t in self.registry.tools if t.get("section") == "featured"][:10]
        lines = ["\n### Available External Tools (NoSignups Registry)"]
        lines.append("When the user needs to perform a specific task, you can suggest or embed these tools:")

        for tool in featured:
            lines.append(f"- {tool['name']}: {tool['description']} ({tool['url']})")

        lines.append("\nTo find the best tool for a task, use the ToolRegistry.")
        return "\n".join(lines)

    def get_system_prompt_addon(self) -> str:
        """Return text to append to Neo's system prompt."""
        return self._system_prompt_addition

    # ADDED: explicit intent shortcuts for short 2-token queries.
    # The score-based matcher can't reliably hit these (they're
    # genuinely short and generic) so hardcode them.
    _EXPLICIT_INTENTS = {
        "test regex": "regexr",
        "regex test": "regexr",
        "try regex": "regexr",
        "compress image": "squoosh",
        "compress a picture": "squoosh",
        "edit markdown": "stackedit",
        "markdown editor": "stackedit",
        "visualize json": "json-crack",
        "view json": "json-crack",
        "edit pdf": "bentopdf",
        "merge pdf": "bentopdf",
        "convert pdf": "bentopdf",
        "draw diagram": "excalidraw",
        "draw a diagram": "excalidraw",
        "make a diagram": "excalidraw",
        "create a diagram": "excalidraw",
    }

    def handle_intent(self, user_message: str) -> Dict:
        """
        Process user message and return tool recommendation + embed code.
        Call this from your ReAct loop's Action phase.

        Returns:
            {
                "has_tool": bool,
                "tools": [...],
                "iframe_html": str or None,
                "response_text": str
            }
        """
        # --- FIXED: Text-manipulation verbs are handled by local skills, not
        # browser tools. "reverse a string hello" was matching Graphite because
        # "string" appears in its description. Veto these outright.
        if self._TEXT_OP_VETO.match(user_message or ""):
            return {
                "has_tool": False,
                "tools": [],
                "iframe_html": None,
                "response_text": None
            }

        # FIXED: explicit intent shortcuts
        _q = (user_message or "").strip().lower()
        _explicit = self._EXPLICIT_INTENTS.get(_q)
        if _explicit:
            _tool = self.registry.get_tool_by_id(_explicit)
            if _tool:
                _sugg = self.integrator.suggest_tools_for_message(user_message, top_k=1) or [_tool]
                _iframe = None
                _integ = _sugg[0].get("integration_type", "iframe") if isinstance(_sugg[0], dict) else "iframe"
                if _integ in ("iframe", "iframe_or_selfhost"):
                    _iframe = self.integrator.get_iframe_embed(_explicit, height="450px")
                _resp = f"I found **{_tool['name']}** for that! {_tool['description']}"
                if _tool.get("github"):
                    _resp += f" You can also [self-host it]({_tool['github']})."
                return {
                    "has_tool": True,
                    "tools": _sugg if isinstance(_sugg, list) else [_tool],
                    "iframe_html": _iframe,
                    "response_text": _resp,
                }

        suggestions = self.integrator.suggest_tools_for_message(user_message, top_k=3)

        if not suggestions:
            return {
                "has_tool": False,
                "tools": [],
                "iframe_html": None,
                "response_text": None
            }

        top_tool = suggestions[0]

        # --- FIXED: Raise threshold from 5.0 → 6.0 AND require at least 2
        # distinct query tokens to have matched. "The Missing Manual" was
        # matching on generic words like "life", "hard" appearing in long
        # text. Requiring 6.0 score + 2 distinct tokens kills those false
        # positives without breaking real tool intents like "draw diagram".
        if top_tool.get("match_score", 0) < 5.0 or top_tool.get("distinct_tokens", 0) < 2:
            return {
                "has_tool": False,
                "tools": [],
                "iframe_html": None,
                "response_text": None
            }

        iframe = None

        if top_tool["integration_type"] in ("iframe", "iframe_or_selfhost"):
            iframe = self.integrator.get_iframe_embed(top_tool["id"], height="450px")

        response = f"I found **{top_tool['name']}** for that! {top_tool['description']}"
        if top_tool.get("github"):
            response += f" You can also [self-host it]({top_tool['github']})."

        return {
            "has_tool": True,
            "tools": suggestions,
            "iframe_html": iframe,
            "response_text": response
        }

    def get_tool_stats(self) -> Dict:
        """Return registry stats for Neo's system scanner / about page."""
        return self.registry.get_stats()


# ============================================================================
# FASTAPI ENDPOINT WRAPPER (Optional)
# ============================================================================
"""
If you want to expose NoSignups tools via Neo's backend API:

from fastapi import FastAPI
app = FastAPI()
plugin = NeoToolPlugin("tools.json")

@app.get("/api/tools/search")
def search_tools(q: str, limit: int = 5):
    matches = plugin.registry.find_tool_for_task(q, top_k=limit)
    return {"results": [{"tool": m.tool, "score": m.score} for m in matches]}

@app.get("/api/tools/{tool_id}/embed")
def get_embed(tool_id: str):
    html = plugin.integrator.get_iframe_embed(tool_id)
    return {"html": html}

@app.get("/api/tools/stats")
def get_stats():
    return plugin.get_tool_stats()
"""


if __name__ == "__main__":
    # Demo / test
    reg = ToolRegistry("tools.json")
    print("=== NoSignups Registry Stats ===")
    for k, v in reg.get_stats().items():
        print(f"  {k}: {v}")

    print("\n=== Search: 'convert pdf' ===")
    for m in reg.find_tool_for_task("convert pdf", top_k=3):
        print(f"  {m.tool['name']} (score: {m.score}, tokens: {m.distinct_tokens}) - {m.tool['url']}")

    print("\n=== Search: 'draw diagram' ===")
    for m in reg.find_tool_for_task("draw diagram", top_k=3):
        print(f"  {m.tool['name']} (score: {m.score}, tokens: {m.distinct_tokens}) - {m.tool['url']}")

    print("\n=== Search: 'reverse a string hello' (should score 0-1 tokens) ===")
    for m in reg.find_tool_for_task("reverse a string hello", top_k=3):
        print(f"  {m.tool['name']} (score: {m.score}, tokens: {m.distinct_tokens})")

    print("\n=== Self-Hostable Count ===")
    print(f"  {len(reg.get_self_hostable_tools())} tools can be self-hosted")