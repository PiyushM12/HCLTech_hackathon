"""Validate citizen / application / appointment CSVs against the Annex C schema and logical rules.

    python scripts/validate_data.py                      # data/synthetic
    python scripts/validate_data.py --dir test_citizens/ # any folder in the Annex C schema

Writes a Markdown report next to the data (validation_report.md) and exits 1 on violations."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = {
    "citizens.csv": ["citizen_id", "full_name", "phone", "date_of_birth", "gender", "district", "residence_type",
                     "annual_household_income", "occupation", "category", "is_disabled", "disability_percent",
                     "land_holding_acres", "preferred_language", "consent_given"],
    "applications.csv": ["application_id", "citizen_id", "scheme_id", "status", "status_updated_on", "remarks"],
    "appointments.csv": ["appointment_id", "citizen_id", "centre_id", "slot_start", "status", "created_at"],
}
FAKE_PHONE = re.compile(r"^000-000-\d{4}$")
RESERVED_CITIZENS = range(9000, 10000)


def _read(p: Path) -> tuple[list[str], list[dict]]:
    with p.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)


def validate(folder: Path, as_of: date, allow_reserved: bool) -> list[str]:
    v: list[str] = []
    data: dict[str, list[dict]] = {}
    for name, cols in REQUIRED.items():
        p = folder / name
        if not p.exists():
            if name == "citizens.csv":
                v.append(f"{name}: file missing")
            continue
        header, rows = _read(p)
        missing = [c for c in cols if c not in header]
        if missing:
            v.append(f"{name}: missing required columns {missing}")
        data[name] = rows
    ids = set()
    for i, r in enumerate(data.get("citizens.csv", []), start=2):
        cid = r.get("citizen_id", "")
        where = f"citizens.csv line {i} ({cid})"
        if not re.fullmatch(r"C\d{4}", cid):
            v.append(f"{where}: citizen_id must be C + 4 digits")
        elif int(cid[1:]) in RESERVED_CITIZENS and not allow_reserved:
            v.append(f"{where}: C9000-C9999 are reserved for judges")
        if cid in ids:
            v.append(f"{where}: duplicate citizen_id")
        ids.add(cid)
        try:
            dob = date.fromisoformat(r["date_of_birth"])
            age = as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))
            if age < 0 or age > 120:
                v.append(f"{where}: age {age} out of range")
        except Exception:
            v.append(f"{where}: date_of_birth must be YYYY-MM-DD")
        if r.get("annual_household_income") not in ("", None):
            try:
                if int(r["annual_household_income"]) < 0:
                    v.append(f"{where}: income is negative")
            except ValueError:
                v.append(f"{where}: income is not an integer")
        if r.get("land_holding_acres") not in ("", None):
            try:
                if float(r["land_holding_acres"]) < 0:
                    v.append(f"{where}: land holding is negative")
            except ValueError:
                v.append(f"{where}: land holding is not a number")
        try:
            dp = int(r.get("disability_percent") or 0)
            if not 0 <= dp <= 100:
                v.append(f"{where}: disability_percent {dp} not in 0-100")
            if r.get("is_disabled") == "N" and dp != 0:
                v.append(f"{where}: is_disabled N but disability_percent {dp}")
        except ValueError:
            v.append(f"{where}: disability_percent is not an integer")
        for col, allowed in [("gender", {"female", "male", "other"}), ("residence_type", {"rural", "urban"}),
                             ("is_disabled", {"Y", "N"}), ("consent_given", {"Y", "N"}),
                             ("preferred_language", {"hi", "en", "kn", "ta"}),
                             ("category", {"general", "obc", "sc", "st", ""})]:
            if r.get(col, "") not in allowed:
                v.append(f"{where}: {col} '{r.get(col)}' not in {sorted(allowed)}")
        if not FAKE_PHONE.match(r.get("phone", "")):
            v.append(f"{where}: phone '{r.get('phone')}' is not an obviously fake number (000-000-NNNN)")
        last4 = r.get("national_id_last4")
        if last4 not in (None, "") and not re.fullmatch(r"\d{4}", last4):
            v.append(f"{where}: only the last four digits of an ID may be stored")
        for col, val in r.items():
            if val and re.search(r"(?<!\d)\d{12}(?!\d)|(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)", val):
                v.append(f"{where}: column {col} looks like a full 12-digit ID")
    for i, r in enumerate(data.get("applications.csv", []), start=2):
        where = f"applications.csv line {i} ({r.get('application_id')})"
        if r.get("citizen_id") not in ids and ids:
            v.append(f"{where}: unknown citizen_id {r.get('citizen_id')}")
        if r.get("status") not in {"draft", "submitted", "approved", "rejected"}:
            v.append(f"{where}: invalid status {r.get('status')}")
        try:
            d = date.fromisoformat(r["status_updated_on"])
            if d > as_of:
                v.append(f"{where}: status_updated_on {d} is in the future")
        except Exception:
            v.append(f"{where}: status_updated_on must be YYYY-MM-DD")
        if r.get("status") == "rejected" and not r.get("remarks"):
            v.append(f"{where}: a rejected application needs a reason in remarks")
    for i, r in enumerate(data.get("appointments.csv", []), start=2):
        where = f"appointments.csv line {i} ({r.get('appointment_id')})"
        if r.get("citizen_id") not in ids and ids:
            v.append(f"{where}: unknown citizen_id")
        if r.get("status") not in {"booked", "cancelled"}:
            v.append(f"{where}: invalid status")
        if r.get("created_at", "") > r.get("slot_start", ""):
            v.append(f"{where}: created after the slot start")
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "data" / "synthetic"))
    ap.add_argument("--as-of", default="2026-11-21")
    ap.add_argument("--allow-reserved", action="store_true", help="allow judge citizen IDs C9000-C9999")
    args = ap.parse_args()
    folder = Path(args.dir)
    violations = validate(folder, date.fromisoformat(args.as_of), args.allow_reserved)
    counts = {}
    for name in REQUIRED:
        p = folder / name
        counts[name] = len(_read(p)[1]) if p.exists() else 0
    report = [f"# Validation report\n", f"Folder: `{folder.name}`  ·  as-of date: {args.as_of}\n",
              "| File | Rows |", "|---|---|"] + [f"| {k} | {v} |" for k, v in counts.items()]
    report += ["", f"**Violations: {len(violations)}**", ""] + [f"- {x}" for x in violations]
    (folder / "validation_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
