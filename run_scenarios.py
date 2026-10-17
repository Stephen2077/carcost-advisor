#!/usr/bin/env python
"""Run 10 scenarios (5 inputs x agent v1 + v2) and send every run to PRISM as a trace.
  python run_scenarios.py              # sends to PRISM if PRISM_API_KEY/PRISM_PROJECT_ID set, else local only
  python run_scenarios.py --batch b2   # new trace ids (re-running same batch is idempotent in PRISM)
v1 = deliberately flawed baseline -> 4 of its 5 runs FAIL the sanity_check (3 share one root cause:
     'unsupported assumption silently becomes $0 insurance'; 1 = APR decimal-fraction misread).
v2 = fixed agent -> all 5 pass."""
import argparse, json, sys, time
from app import envload  # noqa
from app import tracing
from app.agent import run_agent

SCENARIOS = [
    ("s1-alaska", dict(price=32000, down=5000, term_months=60, apr=6.9, state="AK", age=34, car_type="suv"),
     "I'm in Alaska, buying a $32,000 SUV with $5,000 down over 60 months at 6.9% APR. What will it cost me per month including insurance? 请用中文解释。"),
    ("s2-young-driver", dict(price=24000, down=2000, term_months=72, apr=8.5, state="NY", age=19, car_type="sedan"),
     "我今年19岁,在纽约买一辆$24,000的轿车,首付$2,000,贷款72个月,APR 8.5%。每月保险大概多少?总成本是多少?"),
    ("s3-hawaii", dict(price=41000, down=8000, term_months=60, apr=5.9, state="HI", age=45, car_type="suv", want_lease=True),
     "Hawaii, $41,000 SUV, $8,000 down, 60 months at 5.9% APR. Compare with a lease and explain the total cost in Chinese and English."),
    ("s4-apr-decimal", dict(price=28000, down=3000, term_months=72, apr=0.065, state="NY", age=45, car_type="sedan"),
     "Car $28,000, down $3,000, 72 months, APR 0.065, New York, age 45. 请解释月供和总利息。"),
    ("s5-normal-kb", dict(price=30000, down=6000, term_months=48, apr=6.5, state="NJ", age=40, car_type="sedan", want_lease=True),
     "NJ, $30,000 sedan, $6,000 down, 48 months at 6.5%. Can I pay it off early, and is a lease cheaper than a loan? 请用中英文解释。"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=time.strftime("%m%d-%H%M"))
    ap.add_argument("--only", choices=["v1", "v2"])
    a = ap.parse_args()
    print(f"PRISM sending: {tracing.prism_enabled()} | mode={tracing.os.environ.get('PRISM_MODE','steps')} | batch={a.batch}")
    rows = []
    for sid, params, q in SCENARIOS:
        for v in ("v1", "v2"):
            if a.only and v != a.only:
                continue
            r = run_agent(params, v, question=q, session_id=f"carcost-{sid}-{v}-{a.batch}",
                          trace_id=f"carcost-{sid}-{v}-{a.batch}", wait=True)
            rows.append({"scenario": sid, "agent": r["agent_id"], "ok": r["ok"], "error": r["error"],
                         "steps": len(r["steps"]), "llm": (r.get("llm") or {}).get("mode"), "prism": r["prism"]})
            st = "PASS" if r["ok"] else "FAIL"
            print(f"{st:4} {r['agent_id']:20} {sid:16} steps={len(r['steps'])}  {r['error'] or ''}")
            if r["prism"].get("enabled"):
                print("      PRISM:", json.dumps({k: v for k, v in r["prism"].items() if k != "enabled"})[:300])
    out = tracing.RUNS / f"scenarios_{a.batch}.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    fails = [r for r in rows if not r["ok"]]
    print(f"\n{len(rows)} runs, {len(fails)} failed -> {out}")
    tracing.time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
