# core/memory_manager.py
class MemoryManager:
    def __init__(self):
        self.short_term = []  # Last 10 messages
        self.long_term = SQLiteStore("brain.db")
        self.vector = FAISSIndex()
    
    async def retrieve(self, query, k=5):
        # Hybrid: keyword + semantic + recency
        semantic = self.vector.search(query, k)
        factual = self.long_term.query_facts(query)
        recent = self.short_term.get_relevant(query)
        return merge_results(semantic, factual, recent)