# core/telemetry.py
class NeoTelemetry:
    def log_interaction(self, query, plan, tools_used, latency, satisfaction):
        # Store in SQLite for analysis
        pass
    
    def get_stats(self):
        # Most used tools
        # Average plan steps
        # Fallback rate (Groq → Ollama)
        # User satisfaction by personality