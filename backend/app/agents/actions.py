"""Safe actions (R10, Annex A.5): propose -> confirm -> execute -> verify.

Planners only *propose* (an `actions` row with status pending and an expiry). The
executors below are called exclusively by POST /actions/{id}/confirm, after the owner
check. No model output can reach an executor."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from .. import db, i18n, tools
from ..i18n import t
from ..models import PendingAction
from ..nlp import extract, pii


class PlanResult(dict):
    """kind: proposal | info | clarify ; answer ; pending_action ; questions ; tool_calls"""


def _opening(hours: str) -> tuple[time, time]:
    try:
        a, b = hours.split("-")
        return time.fromisoformat(a.strip()), time.fromisoformat(b.strip())
    except Exception:
        return time(10, 0), time(17, 0)


# ------------------------------------------------------------------ booking
def plan_booking(conn: sqlite3.Connection, *, citizen: dict[str, Any], citizen_id: str, message: str,
                 attrs: dict[str, Any], lang: str, as_of: str, conversation_id: str, wants_reminder: bool) -> PlanResult:
    calls: list[dict[str, Any]] = []
    if not citizen.get("found"):
        return PlanResult(kind="clarify", answer=t("need_login", lang), questions=[], tool_calls=calls)
    district = attrs.get("district") or (citizen.get("attributes") or {}).get("district")
    if not district:
        return PlanResult(kind="clarify", answer=t("q_district", lang),
                          questions=[{"attribute": "district", "text": t("q_district", lang), "reason": ""}],
                          tool_calls=calls, pending_attrs=["district"])
    centres = tools.find_service_centres(conn, district, lang)
    calls.append({"tool": "find_service_centres", "input": {"district": district, "language": lang},
                  "output": [{"centre_id": c["centre_id"], "name": c["name"], "working_days": c["working_days"],
                              "working_hours": c["working_hours"], "languages": c["languages"]} for c in centres]})
    if not centres:
        return PlanResult(kind="info", answer=t("no_centre", lang, district=district), tool_calls=calls)
    now = tools.clock(as_of)
    lead_h = int(tools.policy(conn, "appointment_min_lead_hours", as_of))
    horizon = int(tools.policy(conn, "appointment_max_days_ahead", as_of))
    earliest = now + timedelta(hours=lead_h)
    req_day, req_wd = extract.requested_day(message, now.date())
    req_time = extract.requested_time(message) or (11, 0)
    start_day = req_day or earliest.date()
    candidates: list[date] = []
    if req_wd is not None:
        candidates = [start_day + timedelta(weeks=w) for w in range(0, horizon // 7 + 1)]
    candidates += [start_day + timedelta(days=d) for d in range(0, horizon + 1)]
    chosen = None
    centre_closed_on_request = req_day is not None and not any(
        req_day.weekday() in tools.working_weekdays(c["working_days"]) for c in centres)
    for day in candidates:
        if day > now.date() + timedelta(days=horizon):
            continue
        for c in centres:
            if day.weekday() not in tools.working_weekdays(c["working_days"]):
                continue
            open_t, close_t = _opening(c["working_hours"])
            hh, mm = req_time
            slot_t = time(min(max(hh, open_t.hour), close_t.hour - 1), mm if open_t.hour <= hh < close_t.hour else 0)
            slot = datetime.combine(day, slot_t, tzinfo=now.tzinfo)
            if slot >= earliest:
                chosen = (c, slot)
                break
        if chosen:
            break
    if not chosen:
        return PlanResult(kind="info", answer=t("no_centre", lang, district=district), tool_calls=calls)
    centre, slot = chosen
    note = ""
    if req_day and req_day < slot.date() and not centre_closed_on_request:
        note = t("lead_time_note", lang, h=lead_h)
    elif centre_closed_on_request:
        note = t("centre_closed_note", lang, district=district)
    reminder_at = None
    if wants_reminder:
        rt = str(tools.policy(conn, "reminder_default_time", as_of) or "18:00")
        cand = datetime.combine(slot.date() - timedelta(days=1), time.fromisoformat(rt), tzinfo=now.tzinfo)
        reminder_at = cand if cand > now else None
    summary = f"{centre['name']}, {i18n.fmt_slot_en(slot)}"
    reminder_summary = i18n.fmt_slot_en(reminder_at) if reminder_at else None
    payload = {"centre_id": centre["centre_id"], "centre_name": centre["name"], "address": centre["address"],
               "district": district, "slot_start": slot.isoformat(timespec="seconds"),
               "reminder_at": reminder_at.isoformat(timespec="seconds") if reminder_at else None,
               "reminder_text": t("visit_reminder_text", lang, centre=centre["name"], slot=i18n.fmt_slot(slot, lang))}
    pa = tools.propose_action(conn, conversation_id=conversation_id, citizen_id=citizen_id,
                              action_type="book_appointment", payload=payload, summary=summary, tier=1,
                              language=lang, as_of=as_of, reminder=reminder_summary)
    calls.append({"tool": "propose_action", "input": {"action_type": "book_appointment"},
                  "output": {"action_id": pa.action_id, "summary": summary, "reminder": reminder_summary,
                             "slot_start": payload["slot_start"], "expires_at": pa.expires_at}})
    reminder_line = t("reminder_line", lang, when=i18n.fmt_slot(reminder_at, lang)) if reminder_at else ""
    answer = t("book_preview", lang, centre=centre["name"], address=centre["address"],
               slot=i18n.fmt_slot(slot, lang), reminder_line=reminder_line, note=note)
    return PlanResult(kind="proposal", answer=answer, pending_action=pa, tool_calls=calls,
                      evidence=[json.dumps(payload, ensure_ascii=False), f"lead {lead_h} hours"])


def plan_cancel(conn: sqlite3.Connection, *, citizen: dict[str, Any], citizen_id: str, lang: str, as_of: str,
                conversation_id: str) -> PlanResult:
    if not citizen.get("found"):
        return PlanResult(kind="clarify", answer=t("need_login", lang), tool_calls=[])
    now = tools.clock(as_of).isoformat(timespec="seconds")
    appts = db.rows(conn, """SELECT a.*, c.name AS centre_name FROM appointments a LEFT JOIN service_centres c
                             ON a.centre_id=c.centre_id WHERE a.citizen_id=? AND a.status='booked' AND a.slot_start>=?
                             ORDER BY a.slot_start""", (citizen_id, now))
    calls = [{"tool": "get_appointments", "input": {"citizen_id": citizen_id},
              "output": [{"appointment_id": a["appointment_id"], "slot_start": a["slot_start"]} for a in appts]}]
    if not appts:
        return PlanResult(kind="info", answer=t("no_appointment", lang), tool_calls=calls)
    a = appts[0]
    slot = datetime.fromisoformat(a["slot_start"])
    summary = f"{a['appointment_id']}: {a.get('centre_name') or a['centre_id']}, {i18n.fmt_slot_en(slot)}"
    pa = tools.propose_action(conn, conversation_id=conversation_id, citizen_id=citizen_id,
                              action_type="cancel_appointment", payload={"appointment_id": a["appointment_id"]},
                              summary=summary, tier=1, language=lang, as_of=as_of)
    calls.append({"tool": "propose_action", "input": {"action_type": "cancel_appointment"},
                  "output": {"action_id": pa.action_id, "summary": summary}})
    return PlanResult(kind="proposal", answer=t("cancel_preview", lang, summary=summary), pending_action=pa,
                      tool_calls=calls, evidence=[summary, a["slot_start"]])


def plan_reminder(conn: sqlite3.Connection, *, citizen: dict[str, Any], citizen_id: str, scheme: dict[str, Any],
                  status: dict[str, Any], lang: str, as_of: str, conversation_id: str) -> PlanResult:
    if not citizen.get("found"):
        return PlanResult(kind="clarify", answer=t("need_login", lang), tool_calls=[])
    name = i18n.scheme_name(scheme, lang)
    if not status.get("apply_until") or status["status"] != "open":
        return PlanResult(kind="info", answer=t("no_deadline", lang, name=name) if not status.get("apply_until")
                          else t("st_deadline_passed", lang, name=name, date=i18n.fmt_date(status["apply_until"])),
                          tool_calls=[])
    now = tools.clock(as_of)
    rt = time.fromisoformat(str(tools.policy(conn, "reminder_default_time", as_of) or "18:00"))
    deadline = date.fromisoformat(status["apply_until"])
    remind_at = datetime.combine(deadline - timedelta(days=1), rt, tzinfo=now.tzinfo)
    if remind_at <= now:
        remind_at = datetime.combine(deadline, time(9, 0), tzinfo=now.tzinfo)
    if remind_at <= now:
        remind_at = now + timedelta(hours=1)
    text = t("reminder_text", lang, name=name, date=i18n.fmt_date(status["apply_until"]))
    summary = f"Reminder {i18n.fmt_slot_en(remind_at)}: last date for {scheme.get('name_en')} is {status['apply_until']}"
    pa = tools.propose_action(conn, conversation_id=conversation_id, citizen_id=citizen_id, action_type="set_reminder",
                              payload={"remind_at": remind_at.isoformat(timespec="seconds"), "text": text,
                                       "scheme_id": scheme["scheme_id"]},
                              summary=summary, tier=1, language=lang, as_of=as_of, reminder=i18n.fmt_slot_en(remind_at))
    calls = [{"tool": "propose_action", "input": {"action_type": "set_reminder"},
              "output": {"action_id": pa.action_id, "remind_at": remind_at.isoformat(timespec="seconds")}}]
    return PlanResult(kind="proposal", answer=t("reminder_preview", lang, when=i18n.fmt_slot(remind_at, lang), text=text),
                      pending_action=pa, tool_calls=calls, evidence=[status["apply_until"], remind_at.isoformat()])


def plan_draft(conn: sqlite3.Connection, *, citizen: dict[str, Any], citizen_id: str, scheme: dict[str, Any],
               verdict, docs: list[dict[str, Any]], apps: list[dict[str, Any]], lang: str, as_of: str,
               conversation_id: str, extra_attrs: dict[str, Any]) -> PlanResult:
    from .composer import failed_reason  # local import avoids a cycle
    name = i18n.scheme_name(scheme, lang)
    existing = [a for a in apps if a["scheme_id"] == scheme["scheme_id"] and a["status"] in {"draft", "submitted", "approved"}]
    if existing:
        a = existing[0]
        return PlanResult(kind="info", answer=t("already_applied", lang, name=name, status=a["status"],
                                                date=i18n.fmt_date(a["status_updated_on"])), tool_calls=[])
    if verdict.verdict == "not_eligible":
        return PlanResult(kind="info", answer=t("draft_not_eligible", lang, name=name, reason=failed_reason(verdict, lang))
                          + "\n" + t("caveat", lang), tool_calls=[])
    attrs = {**(citizen.get("attributes") or {}), **extra_attrs}
    used = list(dict.fromkeys(r.attribute for r in verdict.rules))
    fields = {"citizen_id": citizen_id, "applicant_name": pii.mask_name(citizen.get("_full_name")),
              "scheme_id": scheme["scheme_id"], "district": attrs.get("district")}
    for a in used:
        if a in attrs:
            fields[a] = attrs[a]
    missing_attrs = [a for a in used if a not in attrs]
    mandatory = [d["document_name"] for d in docs if d.get("mandatory") == "Y"]
    lines = [f"- {i18n.attr_label(k, lang) if k in i18n.ATTR_LABEL else k}: "
             f"{i18n.value_label(k, v, lang) if k in i18n.ATTR_LABEL else v}" for k, v in fields.items() if v not in (None, "")]
    missing_items = [i18n.attr_label(a, lang) for a in missing_attrs] + \
                    [i18n.doc_name(d, lang) for d in docs if d.get("mandatory") == "Y"]
    rejected = [a for a in apps if a["scheme_id"] == scheme["scheme_id"] and a["status"] == "rejected"]
    note = ("\n" + t("rejected_note", lang, name=name, remarks=rejected[0].get("remarks") or "-")) if rejected else ""
    answer = t("draft_preview", lang, name=name, fields="\n".join(lines),
               missing=t("draft_missing", lang, items=", ".join(missing_items)) if missing_items else "") + note
    payload = {"fields": fields, "documents_to_attach": mandatory, "missing_attributes": missing_attrs,
               "eligibility_verdict": verdict.verdict}
    pa = tools.propose_action(conn, conversation_id=conversation_id, citizen_id=citizen_id,
                              action_type="draft_application", payload=payload,
                              summary=f"Draft application for {scheme.get('name_en')} ({scheme['scheme_id']}); status will be 'draft'",
                              tier=2, language=lang, as_of=as_of, missing=missing_attrs + mandatory)
    calls = [{"tool": "propose_action", "input": {"action_type": "draft_application", "scheme_id": scheme["scheme_id"]},
              "output": {"action_id": pa.action_id, "missing": missing_attrs + mandatory}}]
    return PlanResult(kind="proposal", answer=answer, pending_action=pa, tool_calls=calls,
                      evidence=[json.dumps(fields, ensure_ascii=False, default=str)])


# ------------------------------------------------------------------ executors (confirm endpoint only)
def execute(conn: sqlite3.Connection, action: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
    """Run a confirmed action, then read the result back from SQLite to verify it."""
    p = json.loads(action["payload_json"])
    lang = action.get("language") or "en"
    citizen_id = action["citizen_id"]
    as_of = p.get("as_of_date") or tools.now_ist().date().isoformat()
    created = tools.clock(as_of).isoformat(timespec="seconds")
    typ = action["action_type"]
    if typ == "book_appointment":
        apt_id = db.next_id(conn, "appointment", "APT-", 4)
        conn.execute("INSERT INTO appointments VALUES (?,?,?,?,?,?)",
                     (apt_id, citizen_id, p["centre_id"], p["slot_start"], "booked", created))
        result: dict[str, Any] = {"appointment_id": apt_id, "centre_id": p["centre_id"], "slot_start": p["slot_start"]}
        rem_id = None
        if p.get("reminder_at"):
            rem_id = db.next_id(conn, "reminder", "REM-", 4)
            conn.execute("INSERT INTO reminders VALUES (?,?,?,?,?)",
                         (rem_id, citizen_id, p["reminder_at"], p.get("reminder_text") or "", "scheduled"))
            result["reminder_id"] = rem_id
            result["remind_at"] = p["reminder_at"]
        row = db.row(conn, "SELECT status FROM appointments WHERE appointment_id=?", (apt_id,))
        ok = bool(row and row["status"] == "booked") and (
            not rem_id or bool(db.row(conn, "SELECT 1 FROM reminders WHERE reminder_id=? AND status='scheduled'", (rem_id,))))
        msg = t("done_book", lang, summary=p["summary"], id=apt_id)
        if rem_id:
            msg += " " + t("done_reminder", lang, id=rem_id, when=p.get("reminder") or p["reminder_at"])
        return result, ok, msg
    if typ == "cancel_appointment":
        conn.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id=? AND citizen_id=?",
                     (p["appointment_id"], citizen_id))
        row = db.row(conn, "SELECT status FROM appointments WHERE appointment_id=?", (p["appointment_id"],))
        return {"appointment_id": p["appointment_id"], "status": row["status"] if row else None}, \
            bool(row and row["status"] == "cancelled"), t("done_cancel", lang, id=p["appointment_id"])
    if typ == "set_reminder":
        rem_id = db.next_id(conn, "reminder", "REM-", 4)
        conn.execute("INSERT INTO reminders VALUES (?,?,?,?,?)", (rem_id, citizen_id, p["remind_at"], p["text"], "scheduled"))
        row = db.row(conn, "SELECT status FROM reminders WHERE reminder_id=?", (rem_id,))
        return {"reminder_id": rem_id, "remind_at": p["remind_at"]}, bool(row and row["status"] == "scheduled"), \
            t("done_reminder", lang, id=rem_id, when=p.get("reminder") or p["remind_at"])
    if typ == "draft_application":
        app_id = db.next_id(conn, "application", "APP-", 4, start=5001)
        scheme_id = p["fields"]["scheme_id"]
        conn.execute("INSERT INTO applications (application_id, citizen_id, scheme_id, status, status_updated_on, "
                     "remarks, payload_json) VALUES (?,?,?,?,?,?,?)",
                     (app_id, citizen_id, scheme_id, "draft", as_of, "Draft prepared by SchemeSathi; not submitted",
                      db.dumps(p)))
        row = db.row(conn, "SELECT status FROM applications WHERE application_id=?", (app_id,))
        s = tools.scheme_row(conn, scheme_id) or {"name_en": scheme_id}
        return {"application_id": app_id, "scheme_id": scheme_id, "status": row["status"] if row else None}, \
            bool(row and row["status"] == "draft"), t("done_draft", lang, id=app_id, name=i18n.scheme_name(s, lang))
    raise ValueError(f"unknown action type {typ}")


def to_pending(action: dict[str, Any]) -> PendingAction:
    p = json.loads(action["payload_json"])
    return PendingAction(action_id=action["action_id"], action_type=action["action_type"], summary=p.get("summary", ""),
                         reminder=p.get("reminder"), tier=int(p.get("tier", 1)), expires_at=action["expires_at"],
                         status=action["status"], payload=p, missing_fields=p.get("missing_fields", []))
