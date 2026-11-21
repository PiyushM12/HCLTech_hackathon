"""(Re)build SQLite seed data and the Chroma index from data/seed, data/synthetic and the Source Register.

    python scripts/build_kb.py          # skip if already built
    python scripts/build_kb.py --force  # re-embed everything
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kb import ingest  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    report = ingest.build_kb(force=ap.parse_args().force)
    print(json.dumps({k: v for k, v in report.items()}, indent=2, ensure_ascii=False, default=str))
