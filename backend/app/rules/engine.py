"""Deterministic eligibility rule engine (R4, Annex A.3). No LLM is involved.

* Only rule rows in force on as_of_date are used (effective_from <= as_of <= valid_until),
  so an amendment that replaces one clause is just a new row with a later effective_from.
* Rules with an empty rule_group must all pass (AND). Rules sharing a non-empty group are
  alternatives (OR): the group passes if any member passes.
* Verdict per scheme: not_eligible (a required rule or a whole group failed) >
  need_more_information (something unknown) > appears_eligible. A newer amendment that the
  loaded rows do not reflect turns the verdict into verify_with_officer (R9)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .. import db
from ..models import RuleResult, SchemeVerdict

NUMERIC = {"age", "annual_household_income", "land_holding_acres", "disability_percent"}
SENSITIVE = {"category", "is_disabled", "disability_percent"}
ATTR_KIND = {"annual_household_income": "inr", "land_holding_acres": "acres", "disability_percent": "percent",
             "age": "years"}

_GENDER = {"f": "female", "woman": "female", "w": "female", "m": "male", "man": "male", "female": "female",
           "male": "male", "other": "other", "transgender": "other"}
_YES = {"y", "yes", "true", "1", "haan", "ha"}
_NO = {"n", "no", "false", "0", "nahi", "nahin"}


def normalize_attributes(attrs: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (attrs or {}).items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        k = k.strip()
        try:
            if k in {"age", "annual_household_income", "disability_percent"}:
                out[k] = int(round(float(str(v).replace(",", "").replace("₹", ""))))
            elif k == "land_holding_acres":
                out[k] = float(str(v).replace(",", ""))
            elif k == "gender":
                out[k] = _GENDER.get(str(v).strip().lower(), str(v).strip().lower())
            elif k == "is_disabled":
                s = str(v).strip().lower()
                out[k] = "Y" if s in _YES else "N" if s in _NO else str(v).upper()
            elif k in {"occupation", "residence_type", "category"}:
                out[k] = str(v).strip().lower().replace(" ", "_").replace("-", "_")
            elif k == "district":
                out[k] = str(v).strip()
            else:
                out[k] = v
        except (TypeError, ValueError):
            continue
    if out.get("is_disabled") == "N" and "disability_percent" not in out:
        out["disability_percent"] = 0
    return out


def _cmp(actual: Any, op: str, expected: str, attribute: str) -> bool:
    if op in {"in", "not_in"}:
        options = {x.strip().lower() for x in str(expected).split(";") if x.strip()}
        hit = str(actual).strip().lower() in options
        return hit if op == "in" else not hit
    if attribute in NUMERIC:
        a, e = float(actual), float(expected)
    else:
        a, e = str(actual).strip().lower(), str(expected).strip().lower()
    return {"<=": a <= e, ">=": a >= e, "<": a < e, ">": a > e, "=": a == e, "!=": a != e}[op]


def rules_in_force(conn: sqlite3.Connection, scheme_id: str, as_of: str) -> list[dict[str, Any]]:
    return db.rows(conn, """SELECT * FROM eligibility_rules WHERE scheme_id=?
                            AND (effective_from IS NULL OR effective_from='' OR effective_from<=?)
                            AND (valid_until IS NULL OR valid_until='' OR valid_until>=?)
                            ORDER BY rule_id""", (scheme_id, as_of, as_of))


def all_rules(conn: sqlite3.Connection, scheme_id: str) -> list[dict[str, Any]]:
    return db.rows(conn, "SELECT * FROM eligibility_rules WHERE scheme_id=? ORDER BY rule_id", (scheme_id,))


def detect_conflicts(conn: sqlite3.Connection, scheme_id: str, as_of: str,
                     in_force: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Return (conflicts in force, upcoming changes). A conflict is an amendment/circular that
    changes an eligibility value, is in effect, is newer than the loaded rows, and whose values
    are not reflected in any rule row for the scheme."""
    rules = all_rules(conn, scheme_id)
    referenced = {r["source_id"] for r in rules}
    known: set[tuple[str, float]] = set()
    for r in rules:
        kind = ATTR_KIND.get(r["attribute"])
        if kind:
            try:
                known.add((kind, float(r["value"])))
            except ValueError:
                pass
    latest_rule = max((r["effective_from"] or "" for r in in_force), default="")
    conflicts, upcoming = [], []
    effects = db.rows(conn, "SELECT * FROM doc_effects WHERE scheme_id=? AND effect_type='eligibility_change'",
                      (scheme_id,))
    for e in effects:
        values = json.loads(e["values_json"] or "[]")
        unaccounted = [v for v in values if (v["kind"], float(v["value"])) not in known]
        if e["source_id"] in referenced or not unaccounted:
            continue
        item = {"scheme_id": scheme_id, "source_id": e["source_id"], "effective_from": e["effective_from"],
                "type": "amendment_not_in_rule_table", "values": unaccounted,
                "detail": f"{e['source_id']} (effective {e['effective_from']}) changes eligibility values "
                          f"{[v['value'] for v in unaccounted]} that the loaded rule rows do not reflect"}
        if e["effective_from"] and e["effective_from"] > as_of:
            upcoming.append(item)
        elif (e["effective_from"] or "") >= latest_rule:
            conflicts.append(item)
    # future rule rows are upcoming changes too (e.g. an income limit raised from next year)
    for r in rules:
        if r["effective_from"] and r["effective_from"] > as_of:
            upcoming.append({"scheme_id": scheme_id, "source_id": r["source_id"], "effective_from": r["effective_from"],
                             "type": "future_rule", "rule_id": r["rule_id"], "attribute": r["attribute"],
                             "operator": r["operator"], "value": r["value"]})
    return conflicts, upcoming


def evaluate_scheme(conn: sqlite3.Connection, scheme: dict[str, Any], attrs: dict[str, Any],
                    as_of: str, status: dict[str, Any] | None = None) -> SchemeVerdict:
    scheme_id = scheme["scheme_id"]
    in_force = rules_in_force(conn, scheme_id, as_of)
    results: list[RuleResult] = []
    for r in in_force:
        a = r["attribute"]
        actual = attrs.get(a)
        if actual is None:
            res = "unknown"
        else:
            try:
                res = "passed" if _cmp(actual, r["operator"], r["value"], a) else "failed"
            except (TypeError, ValueError):
                res = "unknown"
        results.append(RuleResult(rule_id=r["rule_id"], attribute=a, operator=r["operator"], expected=r["value"],
                                  actual=actual, result=res, rule_group=r["rule_group"] or "",
                                  source_id=r["source_id"] or "", source_section=r["source_section"] or ""))
    failed, unknown = [], []
    groups: dict[str, list[RuleResult]] = {}
    for rr in results:
        if rr.rule_group:
            groups.setdefault(rr.rule_group, []).append(rr)
        elif rr.result == "failed":
            failed.append(rr.rule_id)
        elif rr.result == "unknown":
            unknown.append(rr.attribute)
    for g, members in groups.items():
        if any(m.result == "passed" for m in members):
            continue
        if all(m.result == "failed" for m in members):
            failed.extend(m.rule_id for m in members)
        else:
            unknown.extend(m.attribute for m in members if m.result == "unknown")
    unknown = list(dict.fromkeys(unknown))
    conflicts, upcoming = detect_conflicts(conn, scheme_id, as_of, in_force)
    if not in_force:
        verdict = "verify_with_officer"
        conflicts.append({"scheme_id": scheme_id, "type": "no_rules_in_force",
                          "detail": f"No eligibility rule rows are in force for {scheme_id} on {as_of}"})
    elif failed:
        verdict = "not_eligible"
    elif conflicts:
        verdict = "verify_with_officer"
    elif unknown:
        verdict = "need_more_information"
    else:
        verdict = "appears_eligible"
    st = status or {}
    return SchemeVerdict(
        scheme_id=scheme_id, scheme_name=scheme.get("name_en") or scheme_id,
        scheme_names={k: scheme.get(f"name_{k}") or "" for k in ("en", "hi", "kn", "ta")},
        verdict=verdict, rules=results, unknown=unknown, failed=failed,
        scheme_status=st.get("status", scheme.get("status") or "open"),
        can_apply_now=st.get("status", "open") == "open", apply_until=st.get("apply_until"),
        conflicts=conflicts, upcoming_changes=upcoming)
