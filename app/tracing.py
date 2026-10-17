"""PRISM tracing. Every agent run => 1 trace (POST /api/traces) + spans (POST /api/spans/ingest)
+ SDK trajectory (prismtrace.PRISMtrace.submit_trajectory). Without keys: local JSONL only."""
from __future__ import annotations
import os, json, time, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
import requests
from . import envload  # noqa: F401

RUNS = Path(__file__).resolve().parent.parent / "runs"
RUNS.mkdir(exist_ok=True)
_lock = threading.Lock()
_sdk = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def prism_enabled() -> bool:
    return bool(os.environ.get("PRISM_API_KEY") and os.environ.get("PRISM_PROJECT_ID"))


def host() -> str:
    return os.environ.get("PRISM_HOST", "https://prism.blockconvey.com").rstrip("/")


def sdk_client():
    """prismtrace SDK client (used for trajectory + KB search). None when keys missing."""
    global _sdk
    if not prism_enabled():
        return None
    if _sdk is None:
        try:
            from prismtrace import PRISMtrace
            _sdk = PRISMtrace(api_key=os.environ["PRISM_API_KEY"], host=host(),
                              project_id=os.environ["PRISM_PROJECT_ID"])
        except Exception:
            return None
    return _sdk


class Recorder:
    """Collects spans for one run."""
    def __init__(self, agent_id: str, agent_name: str, session_id: str, trace_id: str):
        self.agent_id, self.agent_name, self.session_id, self.trace_id = agent_id, agent_name, session_id, trace_id
        self.root_id = uuid.uuid4().hex[:16]
        self.spans: list[dict] = []
        self.t0 = time.perf_counter()
        self.start = now_iso()

    def step(self, name: str, span_type: str, input_obj, fn, **kw):
        """Run fn(), record a span. fn returns output obj. Exceptions are recorded then re-raised."""
        sid = uuid.uuid4().hex[:16]
        st, p0 = now_iso(), time.perf_counter()
        status, err, out = "ok", None, None
        try:
            out = fn()
            return out
        except Exception as e:
            status, err = "error", f"{type(e).__name__}: {e}"
            raise
        finally:
            self.spans.append({
                "span_id": sid, "parent_span_id": self.root_id, "name": name, "span_type": span_type,
                "input_text": _txt(input_obj)[:6000], "output_text": _txt(out)[:6000] if out is not None else None,
                "metadata": {"agent_id": self.agent_id, **kw.get("metadata", {})},
                "start_time": st, "end_time": now_iso(), "duration_ms": (time.perf_counter() - p0) * 1000,
                "status": status, "error_message": err, "model": kw.get("model"),
                "token_count_input": kw.get("tokens_in"), "token_count_output": kw.get("tokens_out"),
            })

    def mark_last_error(self, msg: str):
        if self.spans:
            self.spans[-1]["status"] = "error"
            self.spans[-1]["error_message"] = msg

    def root_span(self, input_text: str, output_text: str, status: str, error: str | None):
        return {"span_id": self.root_id, "parent_span_id": None, "name": f"{self.agent_name}.run",
                "span_type": "agent", "input_text": input_text[:6000], "output_text": output_text[:6000],
                "metadata": {"agent_id": self.agent_id}, "start_time": self.start, "end_time": now_iso(),
                "duration_ms": (time.perf_counter() - self.t0) * 1000, "status": status, "error_message": error}


def _txt(o) -> str:
    if o is None: return ""
    return o if isinstance(o, str) else json.dumps(o, ensure_ascii=False, default=str)


def _headers():
    return {"X-PRISMtrace-Key": os.environ["PRISM_API_KEY"], "Content-Type": "application/json"}


def emit(rec: Recorder, *, question: str, params: dict, answer: str, model: str, latency_ms: int,
         ok: bool, error: str | None, tokens_in: int = 0, tokens_out: int = 0, meta: dict | None = None,
         wait: bool = False) -> dict:
    """Write local JSONL always; send to PRISM when configured. Fire-and-forget unless wait=True."""
    spans = [rec.root_span(question, answer, "ok" if ok else "error", error)] + rec.spans
    pid = os.environ.get("PRISM_PROJECT_ID")
    mode = os.environ.get("PRISM_MODE", "steps")
    metadata = {"agent_version": rec.agent_id, "final_status": "success" if ok else "error",
                "failure_reason": error, "params": params, "app": "carcost-advisor", **(meta or {})}
    trace_body = {
        "project_id": pid, "trace_id": rec.trace_id, "model": model,
        "input_messages": [{"role": "user", "content": question + "\n\nPARAMS: " + json.dumps(params, ensure_ascii=False)}],
        "output_message": answer, "latency_ms": latency_ms, "token_count_input": tokens_in,
        "token_count_output": tokens_out, "session_id": rec.session_id, "agent_id": rec.agent_id,
        "agent_name": rec.agent_name, "metadata": metadata,
    }
    spans_body = {"trace_id": rec.trace_id, "project_id": pid, "session_id": rec.session_id,
                  "metadata": {"source": "carcost-advisor", "agent_id": rec.agent_id, "agent_name": rec.agent_name,
                               "final_status": metadata["final_status"]},
                  "spans": spans}
    steps = []
    for s in rec.spans:
        steps.append({"step_type": "tool_call" if s["span_type"] == "tool" else ("reasoning" if s["span_type"] == "llm" else "tool_call"),
                      "label": s["name"], "tool_name": s["name"], "input_summary": (s["input_text"] or "")[:200],
                      "output_summary": (s["output_text"] or "")[:200], "duration_ms": int(s["duration_ms"] or 0),
                      "status": "success" if s["status"] == "ok" else "error"})
    steps.append({"step_type": "final_answer", "label": "final_answer", "output_summary": answer[:200],
                  "duration_ms": 0, "status": "success" if ok else "error"})
    record = {"ts": now_iso(), "trace_id": rec.trace_id, "agent_id": rec.agent_id, "session_id": rec.session_id,
              "ok": ok, "error": error, "question": question, "params": params, "answer": answer, "model": model,
              "spans": spans, "prism": {"enabled": prism_enabled()}}

    def _send_steps():
        """Official SDK path: one trace row per step (ADK-adapter shape: step_order + invocation_id), sharing
        session_id. PRISM assembles them into one trajectory and the trace page shows them as Steps."""
        c = sdk_client()
        res = {"mode": "steps", "rows": 0}
        base = {"framework": "carcost", "agent_name": rec.agent_id, "agent_id": rec.agent_id,
                "source": "carcost-advisor", "session_id": rec.session_id, "invocation_id": rec.trace_id,
                "node_id": f"{rec.agent_id}:{rec.trace_id}", "agent_path": [rec.agent_id],
                "root_agent_name": rec.agent_id, "agent_version": rec.agent_id}
        rows = list(rec.spans)
        has_llm = any(sp["name"] == "llm_explain" for sp in rows)
        if not has_llm:
            rows.append({"name": "final_answer", "span_type": "llm", "duration_ms": 0, "status": "ok"})
        for i, sp in enumerate(rows, 1):
            is_main = sp["name"] in ("llm_explain", "final_answer")
            md = dict(base, step_order=i, step_name=sp["name"],
                      adk_event_type="model_call" if sp["span_type"] == "llm" else "tool_call")
            md["adk_event"] = md["adk_event_type"]
            if not is_main:
                md["tool_name"] = sp["name"]
                if sp["status"] != "ok":
                    md.update(status="error", error_type="StepError", error_message=sp.get("error_message"))
                c.trace_llm(model=f"carcost:tool:{sp['name']}",
                            input_messages=[{"role": "tool_request", "content": (sp.get("input_text") or "")[:8000]}],
                            output=(sp.get("output_text") or sp.get("error_message") or "")[:8000] or "(no output)",
                            latency_ms=int(sp.get("duration_ms") or 0), trace_id=f"{rec.trace_id}.{i:02d}-{sp['name']}",
                            agent_id=rec.agent_id, agent_name=rec.agent_name, session_id=rec.session_id, metadata=md)
            else:
                md.update(metadata); md["adk_event_type"] = md["adk_event"] = "model_call"
                if not ok:
                    md.update(status="error", error_type="AgentFailure", error_message=error)
                c.trace_llm(model=model, input_messages=trace_body["input_messages"], output=answer,
                            latency_ms=latency_ms, token_count_input=tokens_in, token_count_output=tokens_out,
                            trace_id=rec.trace_id, agent_id=rec.agent_id, agent_name=rec.agent_name,
                            session_id=rec.session_id, metadata=md)
            c.flush(timeout=10)  # keep rows in order
            res["rows"] += 1
        res["main_trace_id"] = rec.trace_id
        return res

    def _send():
        res = {}
        if prism_enabled() and mode == "steps" and sdk_client() is not None:
            try:
                res = _send_steps()
            except Exception as e:
                res["error"] = f"{type(e).__name__}: {e}"
        elif prism_enabled():
            try:
                if mode in ("both", "http"):
                    r = requests.post(f"{host()}/api/traces", headers=_headers(), json=trace_body, timeout=20)
                    res["trace"] = {"status": r.status_code, "body": r.text[:200]}
                if mode in ("both", "spans"):
                    r = requests.post(f"{host()}/api/spans/ingest", headers=_headers(), json=spans_body, timeout=20)
                    res["spans"] = {"status": r.status_code, "body": r.text[:200]}
                    c = sdk_client()
                    if c is not None:
                        t = c.submit_trajectory(steps, agent_name=rec.agent_name, agent_id=rec.agent_id,
                                                conversation_id=rec.session_id, request_id=rec.trace_id,
                                                model=model, final_status="success" if ok else "error")
                        res["trajectory"] = bool(t)
            except Exception as e:
                res["error"] = f"{type(e).__name__}: {e}"
        record["prism"].update(res)
        with _lock:
            with open(RUNS / "traces.jsonl", "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return res

    if wait:
        record["prism"].update(_send())
    else:
        threading.Thread(target=_send, daemon=True).start()
    return record["prism"]
