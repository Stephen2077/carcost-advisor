"""Deterministic insurance estimator. ALL TABLES BELOW ARE INVENTED SAMPLE DATA, not real rates.
Returns a RANGE, always labelled ESTIMATE."""
from __future__ import annotations

LABEL = "SAMPLE ESTIMATE ONLY — invented demo tables, not a quote / 示例估算,非真实报价"

# invented base monthly premium (USD) by state
STATE_BASE = {"NY": 210, "NJ": 180, "CA": 190, "TX": 170, "FL": 220, "IL": 150,
              "MA": 140, "WA": 130, "PA": 145, "GA": 175}
OTHER_BASE = 155  # used by v2 for states outside the table (flagged)

AGE_BANDS_V2 = [(16, 20, 2.2), (21, 24, 1.5), (25, 34, 1.1), (35, 59, 1.0), (60, 74, 1.05), (75, 90, 1.25)]
AGE_BANDS_V1 = [(25, 34, 1.1), (35, 59, 1.0), (60, 74, 1.05)]  # v1 only knew these (flaw)
V1_STATES = {"NY", "NJ", "CA", "TX", "FL"}

CAR_FACTOR = {"sedan": 1.0, "suv": 1.08, "truck": 1.12, "ev": 1.25, "sports": 1.5}
SPREAD = 0.18  # +/- 18% around the point estimate


def _age_factor(age: int, bands):
    for lo, hi, f in bands:
        if lo <= age <= hi:
            return f
    return None


def estimate_insurance(p: dict, version: str = "v2") -> dict:
    state, age, ct = p["state"], int(p["age"]), p["car_type"]
    warnings: list[str] = []
    if version == "v1":
        # BUG (deliberate): unsupported state/age silently produce a $0 premium.
        base = STATE_BASE.get(state) if state in V1_STATES else None
        af = _age_factor(age, AGE_BANDS_V1)
        cf = CAR_FACTOR.get(ct)
        if base is None or af is None or cf is None:
            return {"tool": "estimate_insurance", "label": LABEL, "monthly_low": 0.0, "monthly_high": 0.0,
                    "annual_low": 0.0, "annual_high": 0.0, "warnings": [], "version": "v1"}
        pf = 1.0
    else:
        af = _age_factor(age, AGE_BANDS_V2)
        if af is None:
            raise ValueError("driver age outside sample table (16-90) / 驾驶人年龄超出示例表范围(16–90)")
        base = STATE_BASE.get(state)
        if base is None:
            base = OTHER_BASE
            warnings.append(f"State {state} is not in the sample table; used a generic sample base "
                            f"(${OTHER_BASE}/mo). / 州 {state} 不在示例表中,使用通用示例基数 ${OTHER_BASE}/月。")
        cf = CAR_FACTOR.get(ct)
        if cf is None:
            cf = 1.0
            warnings.append(f"Car type '{ct}' unknown; treated as sedan. / 车型 '{ct}' 未知,按轿车处理。")
        pf = min(1.8, max(0.7, (p["price"] / 30000.0) ** 0.5))
    point = base * af * cf * pf
    lo, hi = round(point * (1 - SPREAD)), round(point * (1 + SPREAD))
    return {"tool": "estimate_insurance", "label": LABEL, "version": version,
            "monthly_low": float(lo), "monthly_high": float(hi),
            "annual_low": float(lo * 12), "annual_high": float(hi * 12),
            "factors": {"state_base": base, "age_factor": af, "car_factor": cf, "price_factor": round(pf, 3)},
            "warnings": warnings}
