"""Deterministic tools over SQLite (Annex C "Required tools"). The language model never
computes eligibility, dates, document lists or centre details; it only sees these outputs.

State-changing executors (draft_application, book_appointment, cancel_appointment,
set_reminder) live in agents/actions.py and run only from the confirm endpoint."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import db
from .models import PendingAction, SchemeVerdict
from .rules import engine

IST = timezone(timedelta(hours=5, minutes=30))
WEEKDAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
POLICY_DEFAULTS = {
    "appointment_min_lead_hours": 24, "appointment_max_days_ahead": 30, "action_expiry_minutes": 30,
    "reminder_default_time": "18:00", "grievance_sla_working_days": 30, "referral_sla_working_days_urgent": 1,
    "referral_sla_working_days_high": 2, "referral_sla_working_days_normal": 5,
    "application_processing_target_days": 45, "repeated_contact_threshold": 3, "critic_min_groundedness": 0.8,
    "max_questions_per_turn": 2, "critic_max_revisions": 1, "retrieval_top_k": 6, "application_fee_inr": 0,
}
RECOMMENDED_VERDICTS = {"appears_eligible", "need_more_information"}


def now_ist() -> datetime:
    return datetime.now(IST)


def clock(as_of: str) -> datetime:
    """'Now' on the as_of_date: the real time of day on that date (lets judges test dates)."""
    n = now_ist()
    d = date.fromisoformat(as_of)
    return n.replace(year=d.year, month=d.month, day=d.day)


# ------------------------------------------------------------------ policy registry
def policy_row(conn: sqlite3.Connection, parameter: str, as_of: str | None = None) -> dict[str, Any] | None:
    as_of = as_of or now_ist().date().isoformat()
    return db.row(conn, """SELECT * FROM policy_registry WHERE parameter=? AND
                           (effective_from IS NULL OR effective_from='' OR effective_from<=?)
                           ORDER BY effective_from DESC LIMIT 1""", (parameter, as_of))


def policy(conn: sqlite3.Connection, parameter: str, as_of: str | None = None) -> Any:
    r = policy_row(conn, parameter, as_of)
    raw = r["value"] if r else POLICY_DEFAULTS.get(parameter)
    try:
        f = float(raw)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return raw


# ------------------------------------------------------------------ citizens
def age_on(dob: str, as_of: str) -> int | None:
    try:
        b, d = date.fromisoformat(dob), date.fromisoformat(as_of)
    except (TypeError, ValueError):
        return None
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


PROFILE_ATTRS = ["gender", "district", "residence_type", "annual_household_income", "occupation", "category",
                 "is_disabled", "disability_percent", "land_holding_acres"]
HOUSEHOLD_ATTRS = {"annual_household_income", "district", "residence_type", "category", "land_holding_acres"}


def lookup_citizen(conn: sqlite3.Connection, citizen_id: str, as_of: str) -> dict[str, Any]:
    """Look up the citizen linked to the current account."""
    if not citizen_id or citizen_id == "guest" or citizen_id.startswith(("guest:", "admin:")):
        return {"found": False, "guest": True}
    r = db.row(conn, "SELECT * FROM citizens WHERE citizen_id=?", (citizen_id,))
    if not r:
        return {"found": False, "guest": False}
    consent = (r.get("consent_given") or "N").upper() == "Y"
    out: dict[str, Any] = {"found": True, "citizen_id": citizen_id, "consent_given": "Y" if consent else "N",
                           "preferred_language": r.get("preferred_language")}
    if consent:
        attrs = {k: r.get(k) for k in PROFILE_ATTRS if r.get(k) not in (None, "")}
        age = age_on(r.get("date_of_birth") or "", as_of)
        if age is not None:
            attrs["age"] = age
        out["attributes"] = engine.normalize_attributes(attrs)
        out["_full_name"] = r.get("full_name")  # internal; never put in a response or log
    return out


# ------------------------------------------------------------------ schemes
def list_schemes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return db.rows(conn, "SELECT * FROM schemes ORDER BY scheme_id")


def scheme_row(conn: sqlite3.Connection, scheme_id: str) -> dict[str, Any] | None:
    r = db.row(conn, "SELECT * FROM schemes WHERE scheme_id=?", (scheme_id,))
    if r:
        return r
    if db.row(conn, "SELECT 1 FROM eligibility_rules WHERE scheme_id=? LIMIT 1", (scheme_id,)):
        # rules loaded for a scheme that has no scheme row yet (e.g. judge data): degrade gracefully
        return {"scheme_id": scheme_id, "name_en": scheme_id, "status": "open", "apply_from": "", "apply_until": "",
                "benefit_summary": "", "benefit_type": "other", "source_id": ""}
    return None


def scheme_status(conn: sqlite3.Connection, s: dict[str, Any], as_of: str) -> dict[str, Any]:
    """Effective status and dates on as_of, after applying circulars in force (Annex A.2)."""
    apply_until = s.get("apply_until") or ""
    apply_from = s.get("apply_from") or ""
    notes: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    closure = None
    effects = db.rows(conn, """SELECT * FROM doc_effects WHERE scheme_id=? AND effect_type IN
                               ('deadline_change','closure') ORDER BY effective_from, last_updated""",
                      (s["scheme_id"],))
    for e in effects:
        if e["effective_from"] and e["effective_from"] > as_of:
            upcoming.append({"type": e["effect_type"], "source_id": e["source_id"],
                             "effective_from": e["effective_from"], "new_value": e["new_value"]})
            continue
        if e["effect_type"] == "deadline_change" and apply_until and e["new_value"] > apply_until:
            notes.append({"type": "deadline_extended", "old": apply_until, "new": e["new_value"],
                          "source_id": e["source_id"], "effective_from": e["effective_from"]})
            apply_until = e["new_value"]
        elif e["effect_type"] == "closure":
            closure = e
    if closure:
        status = "closed"
        notes.append({"type": "closed_by_circular", "source_id": closure["source_id"],
                      "effective_from": closure["effective_from"]})
    elif (s.get("status") or "").lower() == "closed":
        status = "closed"
    elif apply_from and as_of < apply_from:
        status = "upcoming"
    elif apply_until and as_of > apply_until:
        status = "closed"
        notes.append({"type": "deadline_passed", "date": apply_until})
    else:
        status = "open"
    days_left = None
    if status == "open" and apply_until:
        days_left = (date.fromisoformat(apply_until) - date.fromisoformat(as_of)).days
    return {"scheme_id": s["scheme_id"], "status": status, "apply_from": apply_from, "apply_until": apply_until,
            "original_apply_until": s.get("apply_until") or "", "days_left": days_left, "notes": notes,
            "upcoming": upcoming, "source_id": s.get("source_id")}


def get_scheme(conn: sqlite3.Connection, scheme_id: str, as_of: str) -> dict[str, Any] | None:
    s = scheme_row(conn, scheme_id)
    if not s:
        return None
    return {**s, "effective": scheme_status(conn, s, as_of)}


def check_eligibility(conn: sqlite3.Connection, attributes: dict[str, Any], scheme_ids: list[str] | None,
                      as_of: str) -> list[SchemeVerdict]:
    attrs = engine.normalize_attributes(attributes)
    if scheme_ids:
        schemes = [s for s in (scheme_row(conn, sid) for sid in scheme_ids) if s]
    else:
        ids = [r["scheme_id"] for r in db.rows(conn, "SELECT DISTINCT scheme_id FROM eligibility_rules")]
        known = {s["scheme_id"]: s for s in list_schemes(conn)}
        schemes = [known.get(i) or scheme_row(conn, i) for i in sorted(set(ids) | set(known))]
        schemes = [s for s in schemes if s]
    out = []
    for s in schemes:
        st = scheme_status(conn, s, as_of)
        eval_date = st["apply_from"] if st["status"] == "upcoming" and st["apply_from"] else as_of
        out.append(engine.evaluate_scheme(conn, s, attrs, eval_date, st))
    return out


def get_required_documents(conn: sqlite3.Connection, scheme_id: str) -> list[dict[str, Any]]:
    return db.rows(conn, """SELECT * FROM required_documents WHERE scheme_id=?
                            ORDER BY CASE mandatory WHEN 'Y' THEN 0 ELSE 1 END, rowid""", (scheme_id,))


# ------------------------------------------------------------------ centres
def working_weekdays(spec: str) -> set[int]:
    spec = (spec or "").strip().lower()
    days: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            ia, ib = WEEKDAY_INDEX.get(a[:3]), WEEKDAY_INDEX.get(b[:3])
            if ia is not None and ib is not None:
                i = ia
                while True:
                    days.add(i)
                    if i == ib:
                        break
                    i = (i + 1) % 7
        elif part[:3] in WEEKDAY_INDEX:
            days.add(WEEKDAY_INDEX[part[:3]])
    return days


def find_service_centres(conn: sqlite3.Connection, district: str | None, language: str | None = None) -> list[dict[str, Any]]:
    if district:
        rows = db.rows(conn, "SELECT * FROM service_centres WHERE lower(district)=lower(?) ORDER BY centre_id", (district,))
    else:
        rows = db.rows(conn, "SELECT * FROM service_centres ORDER BY centre_id")
    lang = {"hinglish": "hi"}.get(language or "", language or "")
    for r in rows:
        r["speaks_language"] = bool(lang and lang in (r.get("languages") or "").split(";"))
        r.pop("contact_phone", None)  # treated as PII; never surfaced through the assistant
    rows.sort(key=lambda r: (not r["speaks_language"], r["centre_id"]))
    return rows


# ------------------------------------------------------------------ applications
def get_applications(conn: sqlite3.Connection, citizen_id: str) -> list[dict[str, Any]]:
    return db.rows(conn, """SELECT application_id, citizen_id, scheme_id, status, status_updated_on, remarks
                            FROM applications WHERE citizen_id=? ORDER BY status_updated_on DESC""", (citizen_id,))


# ------------------------------------------------------------------ actions & referrals
def propose_action(conn: sqlite3.Connection, *, conversation_id: str, citizen_id: str, action_type: str,
                   payload: dict[str, Any], summary: str, tier: int, language: str, as_of: str,
                   reminder: str | None = None, missing: list[str] | None = None) -> PendingAction:
    """Record a proposal only. Nothing is executed until POST /actions/{id}/confirm."""
    action_id = db.next_id(conn, "action", "ACT-", 4, start=1)
    created = clock(as_of)
    expires = created + timedelta(minutes=int(policy(conn, "action_expiry_minutes", as_of)))
    payload = {**payload, "summary": summary, "reminder": reminder, "tier": tier, "missing_fields": missing or [],
               "as_of_date": as_of}
    conn.execute("""INSERT INTO actions (action_id, conversation_id, citizen_id, action_type, payload_json, status,
                    created_at, expires_at, language) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (action_id, conversation_id, citizen_id, action_type, db.dumps(payload), "pending",
                  created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds"), language))
    return PendingAction(action_id=action_id, action_type=action_type, summary=summary, reminder=reminder, tier=tier,
                         expires_at=expires.isoformat(timespec="seconds"), payload=payload, missing_fields=missing or [])


def create_referral(conn: sqlite3.Connection, *, conversation_id: str, citizen_id: str, queue: str, priority: str,
                    bundle: dict[str, Any], as_of: str) -> str:
    rid = db.next_id(conn, "referral", "RF-", 4, start=1)
    conn.execute("""INSERT INTO referrals (referral_id, conversation_id, citizen_id, queue, priority, created_at,
                    bundle_json) VALUES (?,?,?,?,?,?,?)""",
                 (rid, conversation_id, citizen_id, queue, priority, clock(as_of).isoformat(timespec="seconds"),
                  db.dumps(bundle)))
    return rid
