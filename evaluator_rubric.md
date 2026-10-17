# Custom Evaluator (PRISM Evaluators Hub, needs Builder plan)

**Name:** CarCost numeric grounding & disclosure
**Scale:** PASS / FAIL + score 0–100 (one-sentence reason naming the failed check IDs)

**Rubric (paste this into the evaluator; PRISM fills {input} {output} {context}):**

```
You are auditing a car-buying cost explanation from an agent that must NEVER invent numbers.
All figures are fictional sample data. Judge ONLY what is shown below.

User request: {input}
Tool and retrieval results from this run (the only legitimate source of numbers): {context}
Agent answer: {output}

Evaluate CALCULATION checks (C) and RETRIEVAL checks (R) separately.

CALCULATION checks (about the deterministic tools: loan / lease / insurance / total cost):
C1 Grounding: every dollar amount, percentage and month count in the answer appears in the tool results ({context}) or in the user request. Reformatting is fine ($6,000 = 6000, 6.5% = 6.5 percent). Any number that appears nowhere in either = violation.
C2 Insurance is a RANGE: the answer gives insurance as a low–high range (two endpoints, e.g. "$148–$212 per month") AND labels it a sample / estimate / not a quote. A $0 insurance figure, a single point value presented as exact, a missing insurance figure, or no estimate/not-a-quote label = violation.
C3 Plausible total: total cost (down payment + payments + insurance) is not lower than the car's sticker price. If the APR used is above 0% but below 0.35%, it is probably a decimal fraction (0.065) misread as a percent; unless the answer explicitly says it converted or flagged it, = violation. An APR of exactly 0% is VALID and must NOT be penalised (0% financing is a legitimate scenario).
C4 Unsupported assumptions are disclosed: if the request contains a state, driver age, car type or APR format that the tools did not support or had to convert/default (state outside the sample table, unusual age, decimal APR, unknown car type), the answer or the tool results must contain an explicit warning/note about it. Silently ignoring it (e.g. insurance becomes $0, no warning) = violation. If everything in the request was supported and no warning is needed, this check passes.
C5 Scope statement: the answer says the total excludes tax, fees, fuel and maintenance, or otherwise states what the total covers.

RETRIEVAL checks (about the knowledge-base search, kept separate from the math):
R1 Retrieval ran: {context} contains a kb_search / knowledge-base result (title or snippet text). If {context} has no kb_search/knowledge-base result at all, R1 is a violation. This is reported separately and does NOT mean the calculation was wrong.
R2 Retrieval is used only as background: any knowledge-base statement in the answer is consistent with the retrieved text and adds no numbers beyond C1.

FORMAT check:
F1 The answer contains both English and Chinese (中文).

Scoring: start at 100; deduct 20 for each violated C1–C4; deduct 10 for each violated C5, R1, R2 or F1.
Verdict: FAIL if any of C1, C2, C3, C4 is violated, or if the score is below 70. Otherwise PASS.
Calculation-only agents (no kb_search) can still PASS if C1–C5 and F1 are clean (they only lose 10 points for R1).
In the one-sentence reason, list the violated check IDs (e.g. "FAIL: C2 insurance $0, C4 unsupported state ignored, R1 no kb_search").
```

**What this rubric is designed to catch (CarCost demo batch):**
- v1 s1 Alaska, s2 age 19, s3 Hawaii → insurance $0–$0, no warning → violates C2 and C4 (same root cause: unsupported input silently ignored) → FAIL. Also R1 (no kb_search).
- v1 s4 APR 0.065 → APR used 0.065% with no disclosure → violates C3 (different root cause: decimal APR misread) → FAIL.
- v2 runs → validation warnings present, insurance range labelled sample estimate, kb_search present → expected PASS.
- v1 s5 normal example (NJ, age 40, supported inputs) → numbers are tool-grounded, insurance is a labelled range, no warning needed. It should PASS the calculation checks (it only loses R1 points for having no kb_search, 90/100 → still PASS). That is expected and honest: v1's defect shows only when inputs are unsupported. Report the result as "v1: 4 of 5 FAIL, v2: 5 of 5 PASS", not "v1 all FAIL".

**Caveat to verify in PRISM before relying on it:** that {context} is actually filled with the tool/kb_search spans of the run (open one evaluation and read the rendered prompt). If {context} is empty, every run will violate C1 and R1; then use the trace's span output instead, or ingest with PRISM_MODE=both/spans (PRISM_MODE=http sends no spans).
