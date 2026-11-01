from core.knowledge.pdf_engine import search_pdf
from core.knowledge.web_engine import search_web
from core.memory import search_knowledge

def route(query, topic=None):
    pdf_results = search_pdf(query, topic)
    if pdf_results:
        return pdf_results, "pdf"

    web_results = search_web(query)
    if web_results:
        return web_results, "web"

    memory_results = search_knowledge(query, topic)
    if memory_results:
        return memory_results, "memory"

    return [], None
