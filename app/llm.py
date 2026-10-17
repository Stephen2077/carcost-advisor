"""LLM explainer. The model ONLY explains pre-computed, pre-formatted facts. It never calculates.
Real call: Nicrron OpenAI-compatible API. No key (or any error) -> deterministic mock explainer."""
from __future__ import annotations
import os, time, json, re
import requests
from . import envload  # noqa: F401

SYSTEM_V2 = """You are CarCost Advisor's explainer. Reply in plain bilingual text: first English, then Chinese (中文).
HARD RULES:
1. You must NOT calculate, round, add, subtract, convert or estimate any number. Every number you write must be copied
   verbatim from the FACTS block. If a number is not in FACTS, do not write it.
2. State that the insurance figure is a SAMPLE ESTIMATE RANGE from invented tables, not a quote (保险为示例估算区间,非报价).
3. Mention the stated assumptions and any warnings. Mention that total cost excludes tax, fees, fuel, maintenance.
4. No personal financial advice; be neutral, short (max ~170 words per language), use the knowledge-base notes only as background."""

SYSTEM_V1 = """You are a car-buying assistant. Summarize the deal for the customer in English and Chinese.
Use the facts provided and give a total cost picture."""


def _fmt_facts(facts: dict) -> str:
    return json.dumps(facts, ensure_ascii=False, indent=1)


def mock_explain(facts: dict, version: str = "v2") -> str:
    f = facts
    lines_en = [f"Loan: {f['price']} car, {f['down']} down, {f['term_months']} months at {f['apr']} APR "
                f"→ monthly payment {f['monthly_payment']}; total interest {f['total_interest']}; "
                f"total paid on the loan {f['total_paid']}."]
    lines_zh = [f"贷款:车价 {f['price']},首付 {f['down']},{f['term_months']} 个月,APR {f['apr']}"
                f"→ 月供 {f['monthly_payment']};总利息 {f['total_interest']};贷款期内总还款 {f['total_paid']}。"]
    lines_en.append(f"Insurance (SAMPLE ESTIMATE, invented tables, not a quote): {f['insurance_monthly']} per month.")
    lines_zh.append(f"保险(示例估算,虚构表格,非报价):每月 {f['insurance_monthly']}。")
    lines_en.append(f"Total cost over the loan term (down payment + payments + sample insurance): {f['total_cost_range']}. "
                    "Excludes tax, fees, fuel and maintenance.")
    lines_zh.append(f"贷款期内总成本(首付 + 月供 + 示例保险):{f['total_cost_range']}。不含税费、油费、保养。")
    if f.get("lease"):
        L = f["lease"]
        lines_en.append(f"Lease option (sample assumptions): {L['monthly_payment']} per month for {L['term_months']} months, "
                        f"cash out {L['cash_out']}; you own nothing at the end.")
        lines_zh.append(f"租赁选项(示例假设):每月 {L['monthly_payment']},{L['term_months']} 个月,现金支出 {L['cash_out']};期末不拥有车辆。")
    for w in f.get("warnings", []):
        lines_en.append("Note: " + w.split(" / ")[0]); 
        if " / " in w: lines_zh.append("注意:" + w.split(" / ")[1])
    if f.get("kb_notes"):
        lines_en.append("See knowledge base: " + f["kb_notes"][0].split(":")[0].split(" / ")[0])
        lines_zh.append("参考知识库:" + f["kb_notes"][0].split(":")[0].split(" / ")[-1])
    return "English:\n" + "\n".join(lines_en) + "\n\n中文:\n" + "\n".join(lines_zh)


def explain(facts: dict, question: str, version: str = "v2") -> dict:
    """Returns {text, model, mode, latency_ms, tokens_in, tokens_out, error}"""
    key = os.environ.get("NICRRON_API_KEY")
    model = os.environ.get("NICRRON_MODEL", "nicrron/auto")
    base = os.environ.get("NICRRON_BASE_URL", "https://api.nicrron.ai/v1").rstrip("/")
    t0 = time.time()
    if key:
        try:
            system = SYSTEM_V2 if version == "v2" else SYSTEM_V1
            user = f"Customer question: {question}\n\nFACTS (verbatim numbers, already computed by tools):\n{_fmt_facts(facts)}"
            r = requests.post(f"{base}/chat/completions", timeout=45,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                              json={"model": model, "temperature": 0,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]})
            r.raise_for_status()
            j = r.json()
            u = j.get("usage") or {}
            return {"text": j["choices"][0]["message"]["content"], "model": j.get("model", model), "mode": "live",
                    "latency_ms": int((time.time() - t0) * 1000), "tokens_in": u.get("prompt_tokens", 0),
                    "tokens_out": u.get("completion_tokens", 0), "error": None,
                    "system_prompt": system, "user_prompt": user}
        except Exception as e:  # fall back, but record it
            err = f"{type(e).__name__}: {str(e)[:200]}"
            return {"text": mock_explain(facts, version), "model": "mock-explainer", "mode": "mock_fallback",
                    "latency_ms": int((time.time() - t0) * 1000), "tokens_in": 0, "tokens_out": 0, "error": err}
    return {"text": mock_explain(facts, version), "model": "mock-explainer", "mode": "mock",
            "latency_ms": int((time.time() - t0) * 1000), "tokens_in": 0, "tokens_out": 0, "error": None}


_NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def numbers_in(s: str) -> set[float]:
    out = set()
    for m in _NUM.findall(s):
        try:
            out.add(round(float(m.replace(",", "")), 4))
        except ValueError:
            pass
    return out


def number_guard(text: str, facts: dict) -> dict:
    """Every number in the LLM text must appear in FACTS (or the user's own question). Else fail."""
    allowed = numbers_in(json.dumps(facts, ensure_ascii=False)) | {0.0, 1.0, 2.0}
    found = numbers_in(text)
    extra = sorted(found - allowed)
    return {"tool": "number_guard", "ok": not extra, "unknown_numbers": extra, "numbers_checked": len(found)}
