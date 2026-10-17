"""CarCost Advisor agent. Two versions:
 v1 = deliberately naive baseline (no input validation, no kb_search, silent fallbacks, no number guard)
 v2 = fixed agent (validation + warnings, kb_search, honest insurance fallback, number guard)
Numbers come ONLY from deterministic tools (calc.py / insurance.py). The LLM only explains."""
from __future__ import annotations
import time, uuid
from . import calc, insurance, kb, llm, tracing

AGENTS = {"v1": ("carcost-advisor-v1", "CarCost Advisor v1 (baseline)"),
          "v2": ("carcost-advisor-v2", "CarCost Advisor v2 (fixed)")}


def usd(x: float, cents=True) -> str:
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


def rng(lo, hi, cents=False) -> str:
    return f"{usd(lo, cents)}–{usd(hi, cents)}"


def sanity_check(loan: dict, ins: dict, apr_used: float, price: float) -> dict:
    """Invariants any correct answer must satisfy."""
    v = []
    if loan["cash_out_before_insurance"] < price:
        v.append("total paid is less than the sticker price (impossible)")
    if ins["monthly_high"] <= 0:
        v.append("insurance estimate is $0 — unsupported assumption silently ignored")
    if 0 < apr_used < 0.35:
        v.append(f"APR {apr_used}% is implausibly low — probably a decimal fraction entered as a percent")
    return {"tool": "sanity_check", "ok": not v, "violations": v}


def default_question(p: dict) -> str:
    return (f"我想买一辆 ${p['price']:,.0f} 的{p.get('car_type','sedan')},首付 ${p.get('down',0):,.0f},"
            f"贷款 {p['term_months']} 个月,APR {p['apr']}%,在 {p.get('state','NY')},驾驶人 {p.get('age',35)} 岁。"
            f"请解释月供、总利息和保险大概多少。 / Explain the monthly payment, total interest and insurance.")


def run_agent(params: dict, version: str = "v2", question: str | None = None, session_id: str | None = None,
              trace_id: str | None = None, wait: bool = False) -> dict:
    agent_id, agent_name = AGENTS[version]
    user_question = question  # default question is built inside try (after validation for v2), never before it
    question = user_question or ""
    session_id = session_id or f"sess-{uuid.uuid4().hex[:10]}"
    trace_id = trace_id or f"{agent_id}-{uuid.uuid4().hex[:12]}"
    rec = tracing.Recorder(agent_id, agent_name, session_id, trace_id)
    t0 = time.perf_counter()
    prism = tracing.sdk_client()
    warnings: list[str] = []
    error = None
    ok = True
    out: dict = {"version": version, "agent_id": agent_id, "trace_id": trace_id, "session_id": session_id,
                 "question": question}
    try:
        # 1. validate
        if version == "v2":
            p = rec.step("validate_inputs", "tool", params, lambda: calc.validate_inputs(params))
            p, w = p
            warnings += w
            if not user_question:  # build from VALIDATED inputs (v2)
                question = default_question({**{"term_months": 60, "apr": 7, "state": "NY", "age": 35}, **p})
                out["question"] = question
        else:  # v1: trust raw input
            p = dict(params)
            p.update(price=float(p["price"]), down=float(p.get("down", 0)), term_months=int(p["term_months"]),
                     apr=float(p["apr"]), age=int(p.get("age", 35)), state=str(p.get("state", "NY")).upper(),
                     car_type=str(p.get("car_type", "sedan")).lower())
            if not user_question:  # v1 keeps its original behaviour: question built from raw params
                question = default_question({**{"term_months": 60, "apr": 7, "state": "NY", "age": 35}, **params})
                out["question"] = question
        # 2. kb_search (v2 only)
        kb_res = None
        if version == "v2":
            q = "early payoff" if "early" in question.lower() or "提前" in question else \
                "loan term down payment APR monthly payment insurance estimate"
            if p.get("want_lease"): q += " lease vs loan money factor"
            kb_res = rec.step("kb_search", "tool", {"query": q, "limit": 3},
                              lambda: kb.kb_search(q, 3, prism_client=prism, agent_id=None))
        # 3. loan
        loan = rec.step("calculate_loan", "tool", {k: p[k] for k in ("price", "down", "term_months", "apr")},
                        lambda: calc.loan_option(p))
        # 4. lease (optional)
        lease = None
        if p.get("want_lease"):
            lease = rec.step("calculate_lease", "tool", {"price": p["price"], "down": p["down"], "apr": p["apr"]},
                             lambda: calc.lease_option(p))
        # 5. insurance
        ins = rec.step("estimate_insurance", "tool", {k: p[k] for k in ("state", "age", "car_type", "price")},
                       lambda: insurance.estimate_insurance(p, version))
        warnings += ins.get("warnings", [])
        tc = rec.step("total_cost", "tool", {"loan": loan["cash_out_before_insurance"],
                                             "ins": [ins["monthly_low"], ins["monthly_high"]]},
                      lambda: calc.total_cost(loan, ins, p["term_months"]))
        # 6. LLM explain
        facts = {
            "price": usd(p["price"], False), "down": usd(p["down"], False), "term_months": p["term_months"],
            "apr": f"{p['apr']}%", "monthly_payment": usd(loan["monthly_payment"]),
            "total_interest": usd(loan["total_interest"]), "total_paid": usd(loan["total_paid"]),
            "insurance_monthly": rng(ins["monthly_low"], ins["monthly_high"]),
            "insurance_label": "SAMPLE ESTIMATE range from invented tables, not a quote",
            "insurance_annual": rng(ins["annual_low"], ins["annual_high"]),
            "total_cost_range": rng(tc["total_low"], tc["total_high"]),
            "state": p["state"], "driver_age": p["age"], "car_type": p["car_type"],
            "warnings": warnings,
        }
        if lease:
            facts["lease"] = {"monthly_payment": usd(lease["monthly_payment"]), "term_months": lease["term_months"],
                              "cash_out": usd(lease["cash_out_before_insurance"])}
        if kb_res:
            facts["kb_notes"] = [f"{r['title']}: {r['snippet'][:200]}" for r in kb_res["results"][:2]]
        holder = {}

        def _llm():
            r = llm.explain(facts, question, version)
            holder.update(r)
            return r["text"]
        text = rec.step("llm_explain", "llm", {"question": question, "facts": facts}, _llm,
                        model=None)
        rec.spans[-1]["model"] = holder["model"]
        rec.spans[-1]["token_count_input"] = holder.get("tokens_in")
        rec.spans[-1]["token_count_output"] = holder.get("tokens_out")
        rec.spans[-1]["metadata"]["llm_mode"] = holder["mode"]
        # 7. number guard (v2 only)
        guard = None
        if version == "v2":
            guard = rec.step("number_guard", "tool", {"checked": "llm text vs FACTS"},
                             lambda: llm.number_guard(text, facts))
            if not guard["ok"]:
                text = llm.mock_explain(facts, version)
                warnings.append("LLM output contained numbers not in tool results; replaced by deterministic text. / "
                                "LLM 输出含工具结果之外的数字,已替换为确定性文本。")
        # 8. sanity check (invariants)
        chk = rec.step("sanity_check", "tool", {"apr_used": p["apr"]},
                       lambda: sanity_check(loan, ins, p["apr"], p["price"]))
        if not chk["ok"]:
            ok = False
            error = "; ".join(chk["violations"])
            rec.mark_last_error(error)
        out.update({"loan": loan, "lease": lease, "insurance": ins, "total_cost": tc, "kb": kb_res,
                    "explanation": text, "guard": guard, "check": chk, "warnings": warnings,
                    "llm": {k: holder.get(k) for k in ("model", "mode", "latency_ms", "error")},
                    "inputs_used": {k: p[k] for k in ("price", "down", "term_months", "apr", "state", "age", "car_type")}})
        answer, model = text, holder["model"]
        tin, tout = holder.get("tokens_in", 0), holder.get("tokens_out", 0)
    except calc.InputError as e:
        ok, error = False, f"InputError: {e}"
        answer, model, tin, tout = f"Cannot compute: {e}", "none", 0, 0
        out.update({"explanation": answer, "warnings": warnings, "error": error})
    except Exception as e:
        ok, error = False, f"{type(e).__name__}: {e}"
        answer, model, tin, tout = f"Cannot compute: {e}", "none", 0, 0
        out.update({"explanation": answer, "warnings": warnings, "error": error})
    if not question:  # invalid input before a question could be built
        question = f"(invalid input) {str(params)[:200]}"
        out["question"] = question
    latency = int((time.perf_counter() - t0) * 1000)
    out["ok"], out["error"] = ok, error
    out["steps"] = [{"name": s["name"], "type": s["span_type"], "status": s["status"],
                     "ms": int(s["duration_ms"] or 0), "error": s["error_message"],
                     "output": (s["output_text"] or "")[:300]} for s in rec.spans]
    out["prism"] = tracing.emit(rec, question=question, params=params, answer=answer, model=model,
                                latency_ms=latency, ok=ok, error=error, tokens_in=tin or 0, tokens_out=tout or 0,
                                meta={"warnings": warnings}, wait=wait)
    return out
