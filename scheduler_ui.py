"""Scheduler UI — serves /scheduler HTML and /api/scheduler JSON.

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
