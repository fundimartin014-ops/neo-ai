from pathlib import Path

root = Path(".").resolve()

# ============================================================
# FEATURE 2 — SMS plugin (Africa's Talking + Twilio fallback)
# ============================================================
sms_plugin = r'''"""SMS plugin — Africa''s Talking primary, Twilio fallback.

Env vars (either set works):
  Africa''s Talking:  AT_USERNAME, AT_API_KEY, AT_SENDER_ID (optional)
  Twilio:             TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM

Usage from chat:
  sms: +254712345678 Hello from Neo
"""
from __future__ import annotations
import os
import re
import logging

log = logging.getLogger("sms_plugin")

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class Plugin:
    name = "sms"

    def __init__(self):
        self.at_user = os.getenv("AT_USERNAME", "").strip()
        self.at_key = os.getenv("AT_API_KEY", "").strip()
        self.at_sender = os.getenv("AT_SENDER_ID", "").strip()
        self.tw_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.tw_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.tw_from = os.getenv("TWILIO_FROM", "").strip()
        backends = []
        if self.at_user and self.at_key:
            backends.append("africastalking")
        if self.tw_sid and self.tw_token and self.tw_from:
            backends.append("twilio")
        self.backends = backends
        log.info("[SMS] Plugin initialized. Backends: %s",
                 ", ".join(backends) if backends else "none (set AT_* or TWILIO_* env)")

    def run(self):
        return "SMS plugin ready." if self.backends else \
               "SMS plugin idle — no backend configured."

    # ---------- core send ----------
    def send(self, to: str, body: str) -> str:
        to = self._normalize_phone(to)
        if not to:
            return "[SMS] invalid phone number"
        if not body or not body.strip():
            return "[SMS] empty message body"
        for backend in self.backends:
            try:
                if backend == "africastalking":
                    r = self._send_at(to, body)
                    if r: return r
                elif backend == "twilio":
                    r = self._send_twilio(to, body)
                    if r: return r
            except Exception as e:
                log.warning("[SMS] %s failed: %s", backend, e)
        if not self.backends:
            return ("[SMS] no backend configured. Set AT_USERNAME + AT_API_KEY "
                    "or TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM "
                    "in .env, then restart.")
        return "[SMS] all backends failed — check logs"

    # ---------- backends ----------
    def _send_at(self, to: str, body: str) -> str:
        if not _HAS_REQUESTS:
            return ""
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "apiKey": self.at_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"username": self.at_user, "to": to, "message": body}
        if self.at_sender:
            data["from"] = self.at_sender
        r = requests.post(url, headers=headers, data=data, timeout=15)
        if r.status_code >= 300:
            log.warning("[SMS] AT HTTP %s: %s", r.status_code, r.text[:200])
            return ""
        j = r.json()
        recips = (j.get("SMSMessageData") or {}).get("Recipients") or []
        if recips:
            status = recips[0].get("status", "?")
            return f"[SMS] sent via Africa's Talking to {to} ({status})"
        return f"[SMS] sent via Africa's Talking to {to}"

    def _send_twilio(self, to: str, body: str) -> str:
        if not _HAS_REQUESTS:
            return ""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.tw_sid}/Messages.json"
        r = requests.post(url,
                          auth=(self.tw_sid, self.tw_token),
                          data={"To": to, "From": self.tw_from, "Body": body},
                          timeout=15)
        if r.status_code >= 300:
            log.warning("[SMS] Twilio HTTP %s: %s", r.status_code, r.text[:200])
            return ""
        return f"[SMS] sent via Twilio to {to}"

    # ---------- helpers ----------
    @staticmethod
    def _normalize_phone(p: str) -> str:
        if not p:
            return ""
        p = re.sub(r"[^\d+]", "", str(p))
        if p.startswith("0") and len(p) == 10:
            p = "+254" + p[1:]   # Kenya default
        elif p.startswith("254") and not p.startswith("+"):
            p = "+" + p
        if not re.match(r"^\+\d{8,15}$", p):
            return ""
        return p

    # ---------- agent-style interface ----------
    def process(self, query=None, inputs=None, **kw):
        text = ""
        for c in (query, kw.get("text"), kw.get("message")):
            if isinstance(c, str) and c.strip():
                text = c.strip(); break
        if isinstance(inputs, dict):
            text = (inputs.get("to", "") + " " + inputs.get("body", "")).strip() or text
        if not text:
            return "Usage: sms: <phone> <message>"
        m = re.match(r"^(\+?[\d\s\-]{7,20})\s+(.+)$", text)
        if not m:
            return "Usage: sms: <phone> <message>"
        return self.send(m.group(1), m.group(2))

    def handle(self, query=None, **kw):
        return self.process(query=query, **kw)
'''

(root / "core" / "plugins" / "sms_plugin.py").write_text(sms_plugin, encoding="utf-8")
print("[ok] wrote core/plugins/sms_plugin.py")

# ============================================================
# FEATURE 3 — PDF report plugin
# ============================================================
pdf_plugin = r'''"""PDF report plugin — turns chat queries into downloadable PDFs.

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
'''

(root / "core" / "plugins" / "report_plugin.py").write_text(pdf_plugin, encoding="utf-8")
print("[ok] wrote core/plugins/report_plugin.py")

# ============================================================
# FEATURE 4 — Scheduler UI (/scheduler route + auto-refresh page)
# ============================================================
scheduler_ui = r'''"""Scheduler UI — serves /scheduler HTML and /api/scheduler JSON.

Reads state from:
  - data/farm_scheduler_state.json (if present)
  - core/plugins/scheduler_plugin.py's Plugin instance (if loaded)
  - data/scheduler_jobs.json (generic)

Also accepts POST /api/scheduler/run to trigger a job immediately.
"""
from __future__ import annotations
import json
import os
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("scheduler_ui")

STATE_FILE = Path("data") / "farm_scheduler_state.json"
JOBS_FILE  = Path("data") / "scheduler_jobs.json"


def _read_json(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("[SchedulerUI] read %s failed: %s", p, e)
    return None


def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Neo Scheduler</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
       background:#0b1220;color:#e2e8f0;padding:24px;}
  h1{margin:0 0 4px 0;font-size:22px;}
  .sub{color:#64748b;font-size:13px;margin-bottom:20px;}
  .card{background:#111a2e;border:1px solid #1e293b;border-radius:12px;
        padding:16px;margin-bottom:14px;}
  .job{display:flex;align-items:center;justify-content:space-between;
       padding:10px 0;border-bottom:1px solid #1e293b;}
  .job:last-child{border-bottom:none;}
  .job .meta{font-size:12px;color:#94a3b8;margin-top:3px;}
  .badge{display:inline-block;padding:2px 8px;border-radius:999px;
         font-size:11px;font-weight:600;}
  .on{background:#064e3b;color:#6ee7b7;}
  .off{background:#4c1d95;color:#c4b5fd;}
  .run{background:#1d4ed8;color:#fff;border:none;padding:6px 12px;
       border-radius:6px;cursor:pointer;font-size:12px;}
  .run:hover{background:#2563eb;}
  .run:disabled{background:#334155;cursor:not-allowed;}
  .empty{color:#64748b;font-style:italic;padding:10px 0;}
  .stat{margin-right:14px;color:#94a3b8;font-size:12px;}
  code{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:11px;}
</style></head>
<body>
  <h1>⏱️ Scheduler</h1>
  <div class="sub">Scheduled tasks · <span id="last-refresh">loading…</span></div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <strong>Scheduled jobs</strong>
      <div>
        <span class="stat" id="count">0 jobs</span>
        <button class="run" onclick="refresh()">Refresh</button>
      </div>
    </div>
    <div id="jobs"><div class="empty">loading…</div></div>
  </div>

  <div class="card">
    <strong>State files</strong>
    <div class="meta" id="paths"></div>
  </div>

<script>
async function refresh(){
  try{
    const r = await fetch('/api/scheduler');
    const j = await r.json();
    render(j);
  }catch(e){
    document.getElementById('jobs').innerHTML =
      '<div class="empty">failed: '+e+'</div>';
  }
}

function render(j){
  document.getElementById('last-refresh').textContent =
    'refreshed ' + new Date().toLocaleTimeString();
  document.getElementById('count').textContent =
    (j.jobs||[]).length + ' jobs';
  document.getElementById('paths').textContent =
    (j.sources||[]).join(' · ') || '(none)';

  const box = document.getElementById('jobs');
  if(!j.jobs || !j.jobs.length){
    box.innerHTML = '<div class="empty">No jobs configured yet.</div>';
    return;
  }
  box.innerHTML = j.jobs.map((job,i)=>`
    <div class="job">
      <div>
        <div>${job.name || '(unnamed)'}</div>
        <div class="meta">
          ${job.schedule || '?'}
          ${job.goal ? ' · ' + job.goal : ''}
        </div>
      </div>
      <div>
        <span class="badge ${job.enabled ? 'on':'off'}">
          ${job.enabled ? 'ON':'OFF'}
        </span>
        <button class="run" onclick="runJob(${i})">Run</button>
      </div>
    </div>`).join('');
}

async function runJob(idx){
  const r = await fetch('/api/scheduler/run', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({index: idx})
  });
  const j = await r.json();
  alert(j.result || JSON.stringify(j));
  refresh();
}

refresh();
setInterval(refresh, 15000);
</script>
</body></html>"""


def register_scheduler_routes(app, agent_core=None):
    """Call from launcher's NeoAPIServer._setup()."""
    from flask import jsonify, request, Response

    def _collect_jobs():
        jobs = []
        sources = []

        # 1. scheduler_plugin state
        if agent_core:
            orch = agent_core.get("orchestrator")
            if orch:
                plugins = getattr(orch, "plugins", {}) or {}
                for name, p in plugins.items():
                    if "scheduler" not in name:
                        continue
                    for attr in ("jobs", "scheduled", "tasks"):
                        lst = getattr(p, attr, None)
                        if isinstance(lst, list):
                            for j in lst:
                                if isinstance(j, dict):
                                    jobs.append({
                                        "name": j.get("name") or j.get("id") or "job",
                                        "schedule": j.get("schedule") or j.get("cron"),
                                        "goal": j.get("goal") or j.get("task"),
                                        "enabled": bool(j.get("enabled", True)),
                                        "_source": name,
                                    })
                            sources.append(f"plugin:{name}.{attr}")

        # 2. farm_scheduler_state.json
        st = _read_json(STATE_FILE)
        if st:
            if isinstance(st, dict) and "jobs" in st:
                for j in st["jobs"]:
                    jobs.append({
                        "name": j.get("name", "farm_job"),
                        "schedule": j.get("schedule", "daily@06:00"),
                        "goal": j.get("location") or j.get("goal", ""),
                        "enabled": bool(j.get("enabled", True)),
                        "_source": "farm_scheduler_state.json",
                    })
            elif isinstance(st, dict):
                # single job
                jobs.append({
                    "name": st.get("name", "farm_daily_brief"),
                    "schedule": st.get("schedule", "daily@06:00"),
                    "goal": st.get("location", ""),
                    "enabled": bool(st.get("enabled", True)),
                    "_source": "farm_scheduler_state.json",
                })
            sources.append(str(STATE_FILE))

        # 3. generic jobs file
        gen = _read_json(JOBS_FILE)
        if isinstance(gen, list):
            for j in gen:
                jobs.append({
                    "name": j.get("name", "job"),
                    "schedule": j.get("schedule", "?"),
                    "goal": j.get("goal", ""),
                    "enabled": bool(j.get("enabled", True)),
                    "_source": "scheduler_jobs.json",
                })
            sources.append(str(JOBS_FILE))

        return jobs, sources

    @app.route("/scheduler")
    def _scheduler_page():
        return Response(PAGE, mimetype="text/html")

    @app.route("/api/scheduler")
    def _scheduler_api():
        jobs, sources = _collect_jobs()
        return jsonify({
            "jobs": jobs,
            "sources": sources,
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/api/scheduler/run", methods=["POST"])
    def _scheduler_run():
        data = request.get_json() or {}
        idx = data.get("index")
        jobs, _ = _collect_jobs()
        if not isinstance(idx, int) or idx < 0 or idx >= len(jobs):
            return jsonify({"error": "invalid job index"}), 400
        job = jobs[idx]
        goal = job.get("goal") or job.get("name")
        if not agent_core or not goal:
            return jsonify({"result": f"(no agent core — would run: {goal})"})
        orch = agent_core.get("orchestrator")
        if not orch:
            return jsonify({"result": "(no orchestrator)"})
        try:
            import asyncio
            coro = orch.run(goal, [])
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        out = pool.submit(lambda: asyncio.run(coro)).result(timeout=180)
                else:
                    out = loop.run_until_complete(coro)
            except RuntimeError:
                out = asyncio.run(coro)
            return jsonify({"result": str(out)[:500]})
        except Exception as e:
            return jsonify({"result": f"error: {e}"})

    log.info("[SchedulerUI] routes registered at /scheduler")
'''

(root / "scheduler_ui.py").write_text(scheduler_ui, encoding="utf-8")
print("[ok] wrote scheduler_ui.py")

# ============================================================
# Patch launcher.py — register SMS alias + /scheduler + /reports
# ============================================================
lp = root / "launcher.py"
src = lp.read_text(encoding="utf-8")

# 1. Add "sms" and "report" to _AGENT_ALIASES
old_alias = '"speak", "tts",\n    "device", "iot",'
new_alias = '"speak", "tts",\n    "sms", "report",\n    "device", "iot",'
if old_alias in src:
    src = src.replace(old_alias, new_alias, 1)
    print("[ok] added sms + report aliases to launcher")
elif '"sms"' in src and '"report"' in src:
    print("[skip] launcher already has sms/report aliases")
else:
    print("[warn] could not find speak/device alias block — manual edit needed")

# 2. Register scheduler routes + /reports static route in NeoAPIServer._setup
# Find the point after hybrid routes are registered:
hook_anchor = (
    '                logger.info("[Neo] Hybrid UI routes registered at /hybrid")\n'
    '            except Exception as e:\n'
    '                logger.error(f"[Neo] Failed to register hybrid routes: {e}")'
)
hook_insert = hook_anchor + '''

        # ═══ REGISTER SCHEDULER UI (NEW) ═══
        try:
            from scheduler_ui import register_scheduler_routes
            register_scheduler_routes(self.app, agent_core=self.agent_core)
        except Exception as e:
            logger.warning(f"[Neo] scheduler UI not registered: {e}")

        # ═══ SERVE /reports/* (PDF report downloads) ═══
        @self.app.route("/reports/<path:fname>")
        def _reports(fname):
            from flask import send_from_directory
            p = PROJECT_ROOT / "generated_reports"
            if not p.exists():
                return jsonify({"error": "no reports yet"}), 404
            return send_from_directory(str(p), fname)
'''
if hook_anchor in src:
    src = src.replace(hook_anchor, hook_insert, 1)
    print("[ok] added scheduler UI + /reports routes to launcher")
elif "register_scheduler_routes" in src:
    print("[skip] launcher already has scheduler routes")
else:
    print("[warn] could not find hybrid routes block — manual edit needed")

lp.write_text(src, encoding="utf-8")

# ============================================================
# Sanity: compile
# ============================================================
import py_compile
for p in [root/"core"/"plugins"/"sms_plugin.py",
          root/"core"/"plugins"/"report_plugin.py",
          root/"scheduler_ui.py",
          root/"launcher.py"]:
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.relative_to(root)} compiles")
    except py_compile.PyCompileError as e:
        print(f"[fail] {p.relative_to(root)}: {e}")
        raise SystemExit(1)

print()
print("All features written. Add these env vars (whichever you have):")
print("  SMS  → AT_USERNAME, AT_API_KEY[, AT_SENDER_ID]")
print("       or  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM")
print("  PDF  → pip install reportlab   (if not already installed)")
print()
print("Start: python launcher.py --web")