"""Load judge test data in the Annex C schema while the API runs (used immediately).

    python scripts/load_citizens.py --dir test_citizens/

Any of these files may be present: citizens.csv, applications.csv, appointments.csv,
eligibility_rules.csv, schemes.csv, required_documents.csv, service_centres.csv,
policy_registry.csv. Rows are upserted. Same as POST /admin/load."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, loader  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder with CSV files named after the tables")
    args = ap.parse_args()
    db.init_db()
    report = loader.load_dir(args.dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(1 if report["errors"] and not report["loaded"] else 0)


if __name__ == "__main__":
    main()
