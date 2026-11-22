"""Conversation state and audit records (R5 memory, R13 audit). Everything stored here is
PII-redacted first; the audit record holds outcomes and scores, never chain-of-thought."""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from . import db
from .nlp import pii

EMPTY_STATE: dict[str, Any] = {
    "attributes": {}, "subject": "self", "asked": [], "pending_question_attrs": [], "pending_intent": None,
    "last_intent": None, "focus_schemes": [], "question_rounds": 0, "questions_total": 0, "turns": 0,
    "terms_explained": [], "last_action_id": None, "reply_language": None, "referrals": [],
}


def new_trace_id() -> str:
    return uuid.uuid4().hex[:8]


def load_conversation(conn: sqlite3.Connection, conversation_id: str | None, citizen_id: str) -> tuple[str, dict[str, Any], bool]:
    """Return (conversation_id, state, is_new). A conversation belongs to one citizen; another
    caller cannot continue (and so read) it."""
    if conversation_id:
        r = db.row(conn, "SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,))
        if r and r["citizen_id"] == citizen_id:
            state = {**json.loads(json.dumps(EMPTY_STATE)), **json.loads(r["state_json"] or "{}")}
            return conversation_id, state, False
    cid = db.next_id(conn, "conversation", "C-", 4, start=1)
    conn.execute("INSERT INTO conversations (conversation_id, citizen_id, created_at, updated_at, state_json) "
                 "VALUES (?,?,datetime('now'),datetime('now'),?)", (cid, citizen_id, db.dumps(EMPTY_STATE)))
    return cid, json.loads(json.dumps(EMPTY_STATE)), True


def save_state(conn: sqlite3.Connection, conversation_id: str, state: dict[str, Any]) -> None:
    conn.execute("UPDATE conversations SET state_json=?, updated_at=datetime('now') WHERE conversation_id=?",
                 (db.dumps(state), conversation_id))


def add_message(conn: sqlite3.Connection, conversation_id: str, role: str, text: str, trace_id: str | None = None,
                answer_type: str | None = None, route: list[str] | None = None) -> None:
    conn.execute("INSERT INTO messages (conversation_id, role, text, trace_id, answer_type, route_json, created_at) "
                 "VALUES (?,?,?,?,?,?,datetime('now'))",
                 (conversation_id, role, pii.redact(text)[0], trace_id, answer_type, db.dumps(route or [])))


def save_audit(conn: sqlite3.Connection, trace_id: str, conversation_id: str, record: dict[str, Any]) -> None:
    conn.execute("INSERT OR REPLACE INTO audit (trace_id, conversation_id, created_at, record_json) "
                 "VALUES (?,?,datetime('now'),?)", (trace_id, conversation_id, db.dumps(pii.redact_obj(record))))


def get_audit(conn: sqlite3.Connection, trace_id: str) -> dict[str, Any] | None:
    r = db.row(conn, "SELECT record_json FROM audit WHERE trace_id=?", (trace_id,))
    return json.loads(r["record_json"]) if r else None


def append_audit(conn: sqlite3.Connection, trace_id: str, key: str, item: Any) -> None:
    rec = get_audit(conn, trace_id)
    if rec is None:
        return
    rec.setdefault(key, []).append(item)
    conn.execute("UPDATE audit SET record_json=? WHERE trace_id=?", (db.dumps(pii.redact_obj(rec)), trace_id))


def list_conversations(conn: sqlite3.Connection, citizen_id: str) -> list[dict[str, Any]]:
    return db.rows(conn, """SELECT c.conversation_id, c.updated_at,
        (SELECT substr(m.text, 1, 120) FROM messages m WHERE m.conversation_id=c.conversation_id AND m.role='user'
         ORDER BY m.message_id LIMIT 1) AS title
        FROM conversations c WHERE c.citizen_id=?
        ORDER BY c.updated_at DESC,
          (SELECT max(m.message_id) FROM messages m WHERE m.conversation_id=c.conversation_id) DESC""", (citizen_id,))


def get_conversation(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any] | None:
    c = db.row(conn, "SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,))
    if not c:
        return None
    msgs = db.rows(conn, """SELECT m.message_id, m.role, m.text, m.trace_id, m.answer_type, m.route_json,
                           m.created_at, a.record_json FROM messages m LEFT JOIN audit a
                           ON a.trace_id=m.trace_id AND a.conversation_id=m.conversation_id
                           WHERE m.conversation_id=? ORDER BY m.message_id""", (conversation_id,))
    action_rows = {a["action_id"]: a for a in db.rows(conn, "SELECT action_id, status, result_json FROM actions "
                   "WHERE conversation_id=? AND citizen_id=?", (conversation_id, c["citizen_id"]))}
    for m in msgs:
        m["route"] = json.loads(m.pop("route_json") or "[]")
        record = json.loads(m.pop("record_json") or "{}")
        if not record:
            continue
        m["language"] = record.get("reply_language")
        pending = None
        for proposal in record.get("actions_proposed", []):
            action = action_rows.get(proposal["action_id"])
            if action:
                pending = {**proposal, "status": action["status"]}
                m["action_result"] = pii.redact_obj(json.loads(action["result_json"])) if action["result_json"] else None
                break
        m["response"] = {
            "answer_type": m["answer_type"], "intent": record.get("intent"), "critic": record.get("critic"),
            "citations": record.get("citations", []), "questions": record.get("questions_asked", []),
            # Older audit records keep rule checks but lack the full scheme card data.
            "eligibility": [v for v in record.get("rules_evaluated", []) if "scheme_name" in v],
            "pending_action": pending, "referral_id": (record.get("referral") or {}).get("referral_id"),
            "referral": record.get("referral_summary"),
        }
    state = json.loads(c["state_json"] or "{}")
    return {"conversation_id": conversation_id, "citizen_id": c["citizen_id"], "created_at": c["created_at"],
            "messages": msgs, "confirmed_attributes": list((state.get("attributes") or {}).keys()),
            "turns": state.get("turns", 0)}
