"""Tiny .env loader (no dependency). Real environment variables win."""
import os
from pathlib import Path

def load_env():
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and k not in os.environ:
                os.environ[k] = v
    # aliases used by PRISM's own docs
    for a, b in (("PRISMTRACE_API_KEY", "PRISM_API_KEY"), ("PRISMTRACE_PROJECT_ID", "PRISM_PROJECT_ID"),
                 ("PRISMTRACE_HOST", "PRISM_HOST")):
        if os.environ.get(a) and not os.environ.get(b):
            os.environ[b] = os.environ[a]

load_env()
