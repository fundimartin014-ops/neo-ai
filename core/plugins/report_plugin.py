"""PDF report plugin — turns chat queries into downloadable PDFs.

Usage:
  report: <query>          -> generates a PDF report for <query>
  report: farm brief Nakuru

Uses reportlab (pure python, no system deps). Install with:
  pip install reportlab
"""
from __future__ import annotations
import os
import re
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("report_plugin")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak)
    _HAS_RP = True
except ImportError:
    _HAS_RP = False

REPORT_DIR = Path("generated_reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


class Plugin:
    name = "report"

    def __init__(self):
        self.agent_core = None
        self.orch = None
        log.info("[Report] Plugin initialized (reportlab=%s)", _HAS_RP)

    def on_agent_core(self, agent_core):
        self.agent_core = agent_core or {}
        self.orch = self.agent_core.get("orchestrator") if self.agent_core else None

    def run(self):
        return "Report plugin ready."

    # ---------- API ----------
    def generate(self, query: str, body: str = "", title: str = "") -> str:
        if not _HAS_RP:
            return ("[Report] reportlab not installed. Run: "
                    "pip install reportlab")
        query = (query or "").strip()
        if not query:
            return "[Report] empty query"

        title = title or f"Neo Report — {query[:60]}"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_") or "report"
        path = REPORT_DIR / f"{slug}_{stamp}.pdf"

        try:
            self._build_pdf(path, title, query, body)
        except Exception as e:
            log.exception("[Report] PDF build failed")
            return f"[Report] build failed: {e}"

        size = path.stat().st_size
        return (f"[Report] written: {path} ({size} bytes)\n"
                f"Open: http://127.0.0.1:8000/reports/{path.name}")

    # ---------- internals ----------
    def _fetch_body(self, query: str) -> str:
        """Ask the orchestrator to answer the query, then use that as body."""
        if not self.orch:
            return f"(no orchestrator available — report body for: {query})"
        try:
            import asyncio
            coro = self.orch.run(query, [])
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        return pool.submit(lambda: asyncio.run(coro)).result(timeout=120)
                return loop.run_until_complete(coro)
            except RuntimeError:
                return asyncio.run(coro)
        except Exception as e:
            return f"(orchestrator error: {e})"

    def _build_pdf(self, path: Path, title: str, query: str, body: str):
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            textColor=colors.HexColor("#0f172a"), spaceAfter=8)
        meta = ParagraphStyle("meta", parent=styles["Normal"],
                              textColor=colors.HexColor("#64748b"), fontSize=8)
        para = ParagraphStyle("para", parent=styles["BodyText"],
                              fontSize=10.5, leading=14, spaceAfter=6)

        doc = SimpleDocTemplate(str(path), pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=18*mm, bottomMargin=18*mm,
                                title=title)

        story = []
        story.append(Paragraph(title, h1))
        story.append(Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} "
            f"&nbsp;|&nbsp; Query: {query}", meta))
        story.append(Spacer(1, 6*mm))

        # simple sections: split on blank lines / markdown headings
        for chunk in re.split(r"\n\s*\n", body or "(no content)"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if chunk.startswith("## "):
                story.append(Paragraph(chunk[3:], styles["Heading2"]))
            elif chunk.startswith("# "):
                story.append(Paragraph(chunk[2:], styles["Heading1"]))
            else:
                safe = (chunk.replace("&", "&amp;")
                             .replace("<", "&lt;")
                             .replace(">", "&gt;")
                             .replace("\n", "<br/>"))
                story.append(Paragraph(safe, para))

        # metadata table
        story.append(Spacer(1, 8*mm))
        t = Table([["Generated by", "Neo AI"],
                   ["Report type", "Auto-generated"],
                   ["Query", query[:80]]],
                  colWidths=[35*mm, 130*mm])
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), "Helvetica", 9),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#475569")),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#0f172a")),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LINEBELOW", (0,0), (-1,-2), 0.25, colors.HexColor("#e2e8f0")),
        ]))
        story.append(t)
        doc.build(story)

    # ---------- dispatch ----------
    def process(self, query=None, inputs=None, **kw):
        text = ""
        for c in (query, kw.get("text")):
            if isinstance(c, str) and c.strip():
                text = c.strip(); break
        if not text and isinstance(inputs, dict):
            text = str(inputs.get("query") or inputs.get("text") or "").strip()
        if not text:
            return "Usage: report: <query>"
        body = self._fetch_body(text)
        return self.generate(text, body)

    def handle(self, query=None, **kw):
        return self.process(query=query, **kw)
