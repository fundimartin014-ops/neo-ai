"""
core/tool_registry.py
Tool registry with lazy plugin resolution to avoid circular imports.
"""

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, func):
        """Register a tool handler directly."""
        self._tools[name] = func

    def get(self, name):
        """Get a registered tool handler."""
        return self._tools.get(name)

    def list_tools(self):
        """List all registered tool names."""
        return list(self._tools.keys())

    def _resolve_plugin_handler(self, plugin_name, method_name):
        """
        Lazy resolution of plugin methods.
        Call this at runtime, not at module load time.
        """
        try:
            # Try to get from already-loaded plugins if available
            # This avoids hard imports at module level
            import importlib
            import sys
            
            # Check if plugin is already in sys.modules
            module_path = f"core.plugins.{plugin_name}"
            if module_path in sys.modules:
                module = sys.modules[module_path]
                return getattr(module, method_name, None)
            
            # Try dynamic import
            try:
                module = importlib.import_module(module_path)
                return getattr(module, method_name, None)
            except ImportError:
                return None
                
        except Exception:
            return None


# Static catalog for documentation/orchestrator reference only
# Handlers are resolved at runtime, not stored as bare references
TOOL_CATALOG = {
    "web_search": {
        "description": "Search the web for current information",
        "parameters": {"query": "string", "num_results": "int"},
        "plugin": "web_trainer_plugin",
        "method": "search",
        "when_to_use": "User asks about recent events, news, or facts not in memory"
    },
    "github_search": {
        "description": "Search GitHub repositories",
        "parameters": {"query": "string"},
        "plugin": "github_plugin",
        "method": "search_repos",
        "when_to_use": "User asks about code, libraries, or repositories"
    },
    "pdf_query": {
        "description": "Query trained PDF documents",
        "parameters": {"question": "string"},
        "plugin": "pdf_answer_plugin",
        "method": "query",
        "when_to_use": "User asks about content in trained PDFs"
    },
    "memory_search": {
        "description": "Search Neo's memory and knowledge base",
        "parameters": {"query": "string", "top_k": "int"},
        "plugin": "database_plugin",
        "method": "search",
        "when_to_use": "User asks about stored knowledge, past conversations, or trained data"
    },
    "vision_analyze": {
        "description": "Analyze images using vision models",
        "parameters": {"image_path": "string", "prompt": "string"},
        "plugin": "vision_plugin",
        "method": "analyze",
        "when_to_use": "User mentions images, photos, screenshots, or visual content"
    },
    "voice_transcribe": {
        "description": "Transcribe audio to text",
        "parameters": {"audio_source": "string"},
        "plugin": "voice_plugin",
        "method": "transcribe",
        "when_to_use": "User wants to convert speech to text"
    },
    "send_notification": {
        "description": "Send alerts via ntfy.sh or Discord",
        "parameters": {"message": "string", "channel": "string"},
        "plugin": "notification_plugin",
        "method": "notify",
        "when_to_use": "User requests alerts, reminders, or status updates"
    },
    "send_email": {
        "description": "Send email messages",
        "parameters": {"to": "string", "subject": "string", "body": "string"},
        "plugin": "email_plugin",
        "method": "send",
        "when_to_use": "User requests email delivery"
    },
    "spreadsheet": {
        "description": "Create or modify spreadsheets",
        "parameters": {"action": "string", "data": "array", "filename": "string"},
        "plugin": "spreadsheet_plugin",
        "method": "run",
        "when_to_use": "User needs data organization, tables, or CSV generation"
    },
    "schedule_task": {
        "description": "Schedule automated tasks or reminders",
        "parameters": {"task": "string", "schedule": "string"},
        "plugin": "scheduler_plugin",
        "method": "schedule",
        "when_to_use": "User wants cron jobs, delayed execution, or recurring tasks"
    },
    "http_request": {
        "description": "Make HTTP GET/POST requests to APIs",
        "parameters": {"method": "string", "url": "string", "body": "object", "headers": "object"},
        "plugin": "http_plugin",
        "method": "request",
        "when_to_use": "User needs to fetch data from REST APIs or web services"
    },
    "cache_lookup": {
        "description": "Check cached results for recent queries",
        "parameters": {"key": "string"},
        "plugin": "cache_plugin",
        "method": "get",
        "when_to_use": "Avoid redundant API calls or expensive operations"
    },
    "analytics": {
        "description": "Get system analytics and usage statistics",
        "parameters": {"metric": "string"},
        "plugin": "analytics_plugin",
        "method": "get_stats",
        "when_to_use": "User wants performance monitoring or usage reports"
    },
    "system_monitor": {
        "description": "Monitor system health and resources",
        "parameters": {"check": "string"},
        "plugin": "monitor_plugin",
        "method": "check",
        "when_to_use": "User wants to check CPU, memory, disk, or process status"
    },
    "read_logs": {
        "description": "Read system logs",
        "parameters": {"lines": "int", "level": "string"},
        "plugin": "log_plugin",
        "method": "read",
        "when_to_use": "User needs debugging, error investigation, or audit trails"
    },
    "trigger_alert": {
        "description": "Trigger system alerts",
        "parameters": {"type": "string", "message": "string", "severity": "string"},
        "plugin": "alert_plugin",
        "method": "trigger",
        "when_to_use": "Critical notifications or error escalation"
    },
    "track_progress": {
        "description": "Track task progress",
        "parameters": {"task": "string", "status": "string", "note": "string"},
        "plugin": "progress_plugin",
        "method": "update",
        "when_to_use": "Project management, todo tracking, or milestone updates"
    },
    "train_model": {
        "description": "Train on new text data",
        "parameters": {"text": "string", "category": "string", "source": "string"},
        "plugin": "trainer_plugin",
        "method": "train",
        "when_to_use": "Adding knowledge to Neo's memory from raw text"
    },
    "voice_train": {
        "description": "Train voice recognition models",
        "parameters": {"audio_samples": "array", "label": "string"},
        "plugin": "voice_trainer_plugin",
        "method": "train",
        "when_to_use": "Improving STT accuracy with custom vocabulary"
    },
    "browser_search": {
        "description": "Search and extract content from web pages",
        "parameters": {"query": "string"},
        "plugin": "browser_agent",
        "method": "search_and_extract",
        "when_to_use": "Deep web extraction when simple search isn't enough"
    }
}