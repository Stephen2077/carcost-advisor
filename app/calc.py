"""Deterministic finance tools. No LLM ever touches these numbers.
All inputs/outputs are plain dicts so they can be traced as tool spans."""
from __future__ import annotations

MAX_TERM, MIN_TERM = 84, 12


class InputError(ValueError):
    pass


def validate_inputs(p: dict) -> tuple[dict, list[str]]:
    """v2 validation. Returns (clean_params, warnings). Raises InputError on unsupported input."""
    warnings: list[str] = []
    try:
        price = float(p["price"]); down = float(p.get("down", 0))
        term = int(p["term_months"]); apr = float(p["apr"])
    except (KeyError, TypeError, ValueError) as e:
        raise InputError(f"missing/invalid numeric field: {e}")
    if not (1000 <= price <= 500000):
        raise InputError("price must be between $1,000 and $500,000 / 车价需在 $1,000–$500,000")
    if not (0 <= down < price):
        raise InputError("down payment must be >= 0 and less than price / 首付必须小于车价")
    if not (MIN_TERM <= term <= MAX_TERM):
        raise InputError(f"loan term must be {MIN_TERM}-{MAX_TERM} months / 贷款期限需 {MIN_TERM}–{MAX_TERM} 个月")
    if not (0 <= apr <= 40):
        raise InputError("APR must be between 0 and 40 percent / APR 需在 0–40%")
    if 0 < apr < 0.35:
        warnings.append(f"APR {apr} looks like a decimal fraction; interpreted as {round(apr*100, 4)}% — please confirm. / "
                        f"APR {apr} 看起来是小数写法,已按 {round(apr*100, 4)}% 处理,请确认。")
        apr = round(apr * 100, 6)
    age = int(p.get("age", 35))
    clean = dict(p)
    clean.update(price=price, down=down, term_months=term, apr=apr, age=age,
                 state=str(p.get("state", "NY")).upper(), car_type=str(p.get("car_type", "sedan")).lower(),
                 want_lease=bool(p.get("want_lease", False)))
    return clean, warnings


def amortize(principal: float, apr_pct: float, n: int) -> dict:
    """Exact cent-level amortization: payment rounded to cents, last payment absorbs rounding."""
    principal = round(principal, 2)
    if apr_pct == 0:
        pay = round(principal / n, 2)
    else:
        r = apr_pct / 1200.0
        pay = round(principal * r / (1 - (1 + r) ** (-n)), 2)
    bal = principal
    total_interest = 0.0
    total_paid = 0.0
    first_year_interest = 0.0
    last_payment = pay
    for m in range(1, n + 1):
        interest = round(bal * apr_pct / 1200.0, 2)
        pmt = pay if m < n else round(bal + interest, 2)
        bal = round(bal + interest - pmt, 2)
        total_interest += interest
        total_paid += pmt
        if m <= 12:
            first_year_interest += interest
        last_payment = pmt
    return {
        "tool": "calculate_loan",
        "principal": principal, "apr_pct": apr_pct, "term_months": n,
        "monthly_payment": pay, "final_payment": round(last_payment, 2),
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_paid, 2),
        "first_year_interest": round(first_year_interest, 2),
    }


def loan_option(p: dict) -> dict:
    principal = p["price"] - p["down"]
    a = amortize(principal, p["apr"], p["term_months"])
    a["down_payment"] = p["down"]
    a["price"] = p["price"]
    a["cash_out_before_insurance"] = round(p["down"] + a["total_paid"], 2)
    return a


def lease_option(p: dict, term: int = 36, residual_pct: float = 58.0) -> dict:
    """Sample lease math (standard money-factor formula). Residual % is an INVENTED default."""
    cap = p["price"] - p["down"]
    residual = round(p["price"] * residual_pct / 100.0, 2)
    mf = p["apr"] / 2400.0
    dep = (cap - residual) / term
    fin = (cap + residual) * mf
    pay = round(dep + fin, 2)
    return {
        "tool": "calculate_lease", "term_months": term, "residual_pct": residual_pct,
        "residual_value": residual, "money_factor": round(mf, 6),
        "monthly_payment": pay, "down_payment": p["down"],
        "total_lease_payments": round(pay * term, 2),
        "cash_out_before_insurance": round(p["down"] + pay * term, 2),
        "note": "Sample lease assumptions (58% residual, no fees/tax). At lease end you own nothing.",
    }


def total_cost(loan: dict, ins: dict, term: int) -> dict:
    lo = round(loan["cash_out_before_insurance"] + ins["monthly_low"] * term, 2)
    hi = round(loan["cash_out_before_insurance"] + ins["monthly_high"] * term, 2)
    return {"tool": "total_cost", "loan_term_months": term, "total_low": lo, "total_high": hi,
            "scope": "down payment + all loan payments + sample insurance over the loan term; "
                     "excludes tax, fees, fuel, maintenance"}
