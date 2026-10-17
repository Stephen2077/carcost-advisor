from __future__ import annotations
import os, json
from pathlib import Path
from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, JSONResponse
from . import envload  # noqa: F401
from . import kb, tracing
from .agent import run_agent

app = FastAPI(title="CarCost Advisor 买车总成本顾问")
ROOT = Path(__file__).resolve().parent.parent


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text()


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "live (Nicrron)" if os.environ.get("NICRRON_API_KEY") else "mock (no NICRRON_API_KEY)",
            "model": os.environ.get("NICRRON_MODEL", "nicrron/auto"),
            "prism": "sending" if tracing.prism_enabled() else "local-only (no PRISM_API_KEY/PRISM_PROJECT_ID)",
            "prism_mode": os.environ.get("PRISM_MODE", "both")}


@app.get("/api/kb/search")
def kb_search(q: str, limit: int = 3):
    return kb.kb_search(q, limit, prism_client=tracing.sdk_client())


@app.post("/api/advise")
def advise(body: dict = Body(...)):
    version = body.get("version", "v2")
    if version not in ("v1", "v2"):
        version = "v2"
    params = {k: body.get(k) for k in ("price", "down", "term_months", "apr", "state", "age", "car_type", "want_lease")
              if body.get(k) is not None}
    return JSONResponse(run_agent(params, version, question=body.get("question") or None,
                                  session_id=body.get("session_id") or None))


@app.get("/api/runs")
def runs(n: int = 20):
    f = tracing.RUNS / "traces.jsonl"
    if not f.exists():
        return []
    rows = [json.loads(l) for l in f.read_text().splitlines()[-n:]]
    return [{"ts": r["ts"], "trace_id": r["trace_id"], "agent_id": r["agent_id"], "ok": r["ok"], "error": r["error"],
             "prism": r.get("prism")} for r in reversed(rows)]
