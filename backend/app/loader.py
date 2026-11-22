"""CSV loader for the Annex C schema. Used at start-up for the seed data and by judges
(`python scripts/load_citizens.py --dir test_citizens/` or `POST /admin/load`).

Rows are upserted, so loading new rule rows while the API runs takes effect on the next
request (the rule engine reads SQLite every time)."""
from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path
from typing import Iterable

from . import db

# table -> (primary-key columns, required columns from Annex C)
TABLES: dict[str, tuple[list[str], list[str]]] = {
    "schemes": (["scheme_id"], ["scheme_id", "name_en", "name_hi", "name_kn", "name_ta", "department",
                                "benefit_type", "benefit_summary", "status", "apply_from", "apply_until", "source_id"]),
    "eligibility_rules": (["rule_id"], ["rule_id", "scheme_id", "attribute", "operator", "value", "rule_group",
                                        "effective_from", "valid_until", "source_id", "source_section"]),
    "required_documents": (["scheme_id", "document_name"], ["scheme_id", "document_name", "mandatory", "notes"]),
    "service_centres": (["centre_id"], ["centre_id", "name", "district", "block", "address", "working_days",
                                        "working_hours", "languages", "contact_phone"]),
    "citizens": (["citizen_id"], ["citizen_id", "full_name", "phone", "date_of_birth", "gender", "district",
                                  "residence_type", "annual_household_income", "occupation", "category",
                                  "is_disabled", "disability_percent", "land_holding_acres",
                                  "preferred_language", "consent_given"]),
    "applications": (["application_id"], ["application_id", "citizen_id", "scheme_id", "status",
                                          "status_updated_on", "remarks"]),
    "appointments": (["appointment_id"], ["appointment_id", "citizen_id", "centre_id", "slot_start", "status", "created_at"]),
    "reminders": (["reminder_id"], ["reminder_id", "citizen_id", "remind_at", "text", "status"]),
    "policy_registry": (["rule_id"], ["rule_id", "description", "parameter", "operator", "value",
                                      "scope_schemes", "effective_from", "source_id", "source_section"]),
}
VALID_ATTRIBUTES = {"age", "annual_household_income", "land_holding_acres", "gender", "category", "district",
                    "residence_type", "is_disabled", "disability_percent", "occupation"}
VALID_OPERATORS = {"<=", ">=", "=", "!=", "in", "not_in", "<", ">"}


def table_for_filename(name: str) -> str | None:
    stem = Path(name).stem.lower()
    for t in TABLES:
        if stem == t or stem.startswith(t):
            return t
    aliases = {"rules": "eligibility_rules", "documents": "required_documents", "centres": "service_centres",
               "policy": "policy_registry", "citizen": "citizens"}
    return aliases.get(stem)


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _validate_row(table: str, r: dict[str, str]) -> str | None:
    if table == "eligibility_rules":
        if r.get("attribute") not in VALID_ATTRIBUTES:
            return f"rule {r.get('rule_id')}: unknown attribute '{r.get('attribute')}'"
        if r.get("operator") not in VALID_OPERATORS:
            return f"rule {r.get('rule_id')}: unknown operator '{r.get('operator')}'"
    if table == "applications" and r.get("status") not in {"draft", "submitted", "approved", "rejected"}:
        return f"application {r.get('application_id')}: invalid status '{r.get('status')}'"
    if table == "citizens":
        cid = r.get("citizen_id", "")
        if not (len(cid) == 5 and cid[0] == "C" and cid[1:].isdigit()):
            return f"citizen {cid}: id must be C followed by 4 digits"
    return None


def load_rows(conn: sqlite3.Connection, table: str, rows: Iterable[dict[str, str]]) -> tuple[int, list[str]]:
    pk, required = TABLES[table]
    cols = _table_columns(conn, table)
    count, errors = 0, []
    for i, raw in enumerate(rows, start=2):
        r = {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k}
        missing = [c for c in pk if not r.get(c)]
        if missing:
            errors.append(f"{table} line {i}: missing key {missing}")
            continue
        err = _validate_row(table, r)
        if err:
            errors.append(f"{table} line {i}: {err}")
            continue
        use = [c for c in cols if c in r]
        values = [r[c] if r[c] != "" else None for c in use]
        # keep empty strings for rule_group / valid_until / apply_until semantics
        values = ["" if (v is None and c in {"rule_group", "valid_until", "apply_until", "remarks"}) else v
                  for c, v in zip(use, values)]
        if table == "eligibility_rules":
            use.append("loaded_at")
            values.append(__import__("datetime").datetime.now().isoformat(timespec="seconds"))
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({','.join(use)}) VALUES ({','.join('?' * len(use))})", values)
        count += 1
    return count, errors


def load_csv_text(conn: sqlite3.Connection, table: str, text: str) -> tuple[int, list[str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    _, required = TABLES[table]
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in required if c not in header]
    if missing:
        return 0, [f"{table}: missing required columns {missing}"]
    return load_rows(conn, table, reader)


def load_dir(directory: str | Path) -> dict:
    directory = Path(directory)
    report: dict = {"loaded": {}, "errors": []}
    order = list(TABLES)  # schemes before rules before citizens before applications
    files = sorted(directory.glob("*.csv"), key=lambda p: order.index(table_for_filename(p.name))
                   if table_for_filename(p.name) in order else 99)
    with db.get_conn() as conn:
        for f in files:
            table = table_for_filename(f.name)
            if not table:
                report["errors"].append(f"{f.name}: no matching table, skipped")
                continue
            n, errs = load_csv_text(conn, table, f.read_text(encoding="utf-8"))
            report["loaded"][table] = report["loaded"].get(table, 0) + n
            report["errors"].extend(errs)
    return report
