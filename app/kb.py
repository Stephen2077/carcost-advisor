"""Small local knowledge base + kb_search tool. If PRISM_API_KEY is set the PRISM KB is tried first."""
from __future__ import annotations
import re, os
from pathlib import Path

KB_FILE = Path(__file__).resolve().parent.parent / "kb" / "carcost_faq.md"


def _load():
    docs, cur = [], None
    for line in KB_FILE.read_text().splitlines():
        if line.startswith("## "):
            if cur: docs.append(cur)
            cur = {"id": f"kb-{len(docs)+1}", "title": line[3:].strip(), "text": ""}
        elif cur is not None:
            cur["text"] += line + "\n"
    if cur: docs.append(cur)
    for d in docs: d["text"] = d["text"].strip()
    return docs

DOCS = _load()


def _tokens(s: str) -> set[str]:
    s = s.lower()
    words = set(re.findall(r"[a-z0-9]{2,}", s))
    cjk = re.findall(r"[\u4e00-\u9fff]", s)
    bigrams = {a + b for a, b in zip(cjk, cjk[1:])}
    return words | bigrams


def kb_search_local(query: str, limit: int = 3) -> list[dict]:
    q = _tokens(query)
    scored = []
    for d in DOCS:
        t = _tokens(d["title"] + " " + d["text"])
        title_t = _tokens(d["title"])
        score = len(q & t) + 2 * len(q & title_t)
        if score: scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [{"id": d["id"], "title": d["title"], "snippet": d["text"][:420], "score": s, "source": "local-kb"}
            for s, d in scored[:limit]]


def kb_search(query: str, limit: int = 3, prism_client=None, agent_id: str | None = None) -> dict:
    """Tool entry point. Returns {tool, query, results, backend}."""
    backend = "local"
    results = None
    fallback_reason = None
    if prism_client is not None and os.environ.get("KB_BACKEND", "auto") in ("auto", "prism"):
        try:
            r = prism_client.kb_search(query, agent_id=agent_id, limit=limit)
            if r:
                results = [{"id": str(x.get("id") or x.get("doc_id") or i),
                            "title": str(x.get("title") or x.get("filename") or "PRISM KB"),
                            "snippet": str(x.get("content") or x.get("text") or x.get("snippet") or x)[:420],
                            "score": x.get("score"), "source": "prism-kb"} for i, x in enumerate(r)]
                backend = "prism"
            else:
                fallback_reason = "prism_kb_empty_result"
        except Exception as e:
            results = None
            fallback_reason = f"prism_kb_error: {type(e).__name__}: {str(e)[:120]}"
    if not results:
        results = kb_search_local(query, limit)
    out = {"tool": "kb_search", "query": query, "backend": backend, "results": results}
    if backend == "local" and fallback_reason:  # PRISM KB was tried but failed/empty -> make it visible in the span output
        out["fallback"] = True
        out["fallback_reason"] = fallback_reason
    return out
