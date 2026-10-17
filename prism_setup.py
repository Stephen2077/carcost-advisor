#!/usr/bin/env python
"""PRISM helper. python prism_setup.py [--handshake] [--upload-kb] [--kb-test "query"]"""
import argparse, json, os, requests
from app import envload  # noqa
from app import tracing

ap = argparse.ArgumentParser()
ap.add_argument("--handshake", action="store_true", help="prove key + store a test trace, then setup-doctor")
ap.add_argument("--upload-kb", action="store_true", help="upload kb/carcost_faq.md to the PRISM Knowledge Base (project-wide)")
ap.add_argument("--kb-test", metavar="QUERY")
a = ap.parse_args()
if not tracing.prism_enabled():
    raise SystemExit("PRISM_API_KEY / PRISM_PROJECT_ID not set (see .env.example)")
H, pid = tracing.host(), os.environ["PRISM_PROJECT_ID"]
hdr = tracing._headers()
if a.handshake:
    r = requests.post(f"{H}/api/setup-doctor/handshake", headers=hdr, json={"project_id": pid, "send_test_trace": True}, timeout=20)
    print("handshake", r.status_code, r.text[:400])
    r = requests.get(f"{H}/api/setup-doctor", params={"project_id": pid}, headers=hdr, timeout=20)
    print("setup-doctor", r.status_code, r.text[:600])
c = tracing.sdk_client()
if a.upload_kb:
    from pathlib import Path
    p = Path("kb/carcost_faq.md")
    print("kb_upload:", c.kb_upload(p.name, p.read_text(), description="CarCost Advisor sample FAQ (demo data)"))
if a.kb_test:
    print(json.dumps(c.kb_search(a.kb_test, limit=3), ensure_ascii=False, indent=1)[:1500])
