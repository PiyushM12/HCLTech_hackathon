"""FastAPI app: the API contract in Section 6 of the participant guide, plus small read-only
helpers the UI uses (/schemes, /sources/{id}, /citizens/demo) and an admin CSV loader."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import auth, config, db, i18n, loader, memory, tools
from .agents import actions
from .graph import run_ask
from .kb import ingest as kb_ingest
from .kb import vectorstore as vs
from .llm import llm
from .models import AskRequest, AskResponse, EligibilityRequest, LoginRequest


log = logging.getLogger("schemesathi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    with db.get_conn() as conn:
        auth.seed_admin(conn)
    report = kb_ingest.build_kb()
    log.info("knowledge base ready: %s", {k: v for k, v in report.items() if k != "seed"})
    vs.get_embedder()  # warm the model so the first request is not slow
    yield


app = FastAPI(title="SchemeSathi API", version="1.0.0", lifespan=lifespan,
              description="Multilingual citizen scheme navigator for the fictional state of Mitrapur Pradesh. "
                          "All schemes, amounts and offices are fictional; nothing here is real advice.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def _cid(x_citizen_id: Optional[str]) -> str:
    v = (x_citizen_id or "guest").strip()
    return v if v else "guest"


# ------------------------------------------------------------------ authentication
@app.post("/auth/login")
def login(req: LoginRequest) -> dict[str, Any]:
    with db.get_conn() as conn:
        user = auth.authenticate(conn, req.username, req.password)
    if not user:
        raise HTTPException(401, "wrong username or password")
    token, exp = auth.make_token(user["username"], user["role"], user["citizen_id"])
    return {"token": token, "token_type": "bearer", "expires_at": exp, "username": user["username"],
            "role": user["role"], "citizen_id": user["citizen_id"]}


@app.get("/auth/me")
def me(user: dict = Depends(auth.require_user)) -> dict[str, Any]:
    out = {"username": user["sub"], "role": user["role"], "citizen_id": user["citizen_id"], "expires_at": user["exp"]}
    if user["citizen_id"]:
        with db.get_conn() as conn:
            c = db.row(conn, "SELECT district, residence_type, preferred_language, consent_given FROM citizens "
                             "WHERE citizen_id=?", (user["citizen_id"],))
        out["profile"] = c
    return out


# ------------------------------------------------------------------ core contract
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, x_citizen_id: Optional[str] = Header(default="guest"),
        user: Optional[dict] = Depends(auth.current_user)) -> AskResponse:
    return run_ask(req, auth.resolve_citizen(user, x_citizen_id))


@app.post("/eligibility")
def eligibility(req: EligibilityRequest) -> dict[str, Any]:
    as_of = req.as_of_date or tools.now_ist().date().isoformat()
    with db.get_conn() as conn:
        res = tools.check_eligibility(conn, req.attributes, req.scheme_ids, as_of)
    if not req.include_not_eligible:  # the UI shows only schemes the citizen can act on
        res = [r for r in res if r.verdict != "not_eligible" and r.scheme_status != "closed"]
    return {"as_of_date": as_of, "results": [r.model_dump() for r in res]}


def _load_action(conn, action_id: str, citizen_id: str) -> dict[str, Any]:
    a = db.row(conn, "SELECT * FROM actions WHERE action_id=?", (action_id,))
    if not a:
        raise HTTPException(404, "action not found")
    if a["citizen_id"] != citizen_id:
        raise HTTPException(403, "only the citizen who owns this action can confirm or cancel it")
    return a


@app.post("/actions/{action_id}/confirm")
def confirm(action_id: str, x_citizen_id: Optional[str] = Header(default="guest"),
            user: Optional[dict] = Depends(auth.current_user)) -> dict[str, Any]:
    cid = auth.resolve_citizen(user, x_citizen_id)
    trace_id = memory.new_trace_id()
    with db.get_conn() as conn:
        a = _load_action(conn, action_id, cid)
        lang = a.get("language") or "en"
        if a["status"] == "executed":  # idempotent: a second call returns the same result
            stored = json.loads(a["result_json"] or "{}")
            return {**stored, "repeat": True}
        if a["status"] == "cancelled":
            raise HTTPException(409, "this action was cancelled; nothing was executed")
        payload = json.loads(a["payload_json"])
        now = tools.clock(payload.get("as_of_date") or tools.now_ist().date().isoformat())
        if a["status"] == "expired" or datetime.fromisoformat(a["expires_at"]) < now:
            conn.execute("UPDATE actions SET status='expired' WHERE action_id=?", (action_id,))
            conn.commit()
            raise HTTPException(410, "this proposal has expired; please ask again")
        result, verified, message = actions.execute(conn, a)
        a["status"] = "executed"
        pa = actions.to_pending(a)
        response = {"trace_id": trace_id, "answer_type": "action_completed", "language": lang, "answer": message,
                    "action": pa.model_dump(), "result": result, "verified": verified}
        conn.execute("UPDATE actions SET status='executed', result_json=?, executed_at=? WHERE action_id=?",
                     (db.dumps(response), now.isoformat(timespec="seconds"), action_id))
        memory.add_message(conn, a["conversation_id"], "system", f"[confirmed {action_id}]")
        memory.add_message(conn, a["conversation_id"], "assistant", message, trace_id, "action_completed",
                           ["confirm", "execute", "verify"])
        memory.save_audit(conn, trace_id, a["conversation_id"], {
            "trace_id": trace_id, "conversation_id": a["conversation_id"], "citizen_id": cid,
            "answer_type": "action_completed", "route": ["confirm", "execute", "verify"],
            "actions_confirmed": [{"action_id": action_id, "action_type": a["action_type"], "result": result,
                                   "verified": verified, "confirmed_at": now.isoformat(timespec="seconds")}],
            "model": {"mode": "none (deterministic executor)"}})
        # link the confirmation back to the audit record of the turn that proposed it
        for r in db.rows(conn, "SELECT trace_id FROM messages WHERE conversation_id=? AND answer_type='confirmation_needed'",
                         (a["conversation_id"],)):
            rec = memory.get_audit(conn, r["trace_id"])
            if rec and any(p.get("action_id") == action_id for p in rec.get("actions_proposed", [])):
                memory.append_audit(conn, r["trace_id"], "actions_confirmed",
                                    {"action_id": action_id, "confirmed_by_trace": trace_id, "verified": verified})
        return response


@app.post("/actions/{action_id}/cancel")
def cancel(action_id: str, x_citizen_id: Optional[str] = Header(default="guest"),
           user: Optional[dict] = Depends(auth.current_user)) -> dict[str, Any]:
    cid = auth.resolve_citizen(user, x_citizen_id)
    with db.get_conn() as conn:
        a = _load_action(conn, action_id, cid)
        lang = a.get("language") or "en"
        if a["status"] == "executed":
            raise HTTPException(409, "this action was already executed; ask to cancel the booking instead")
        if a["status"] != "cancelled":
            conn.execute("UPDATE actions SET status='cancelled' WHERE action_id=?", (action_id,))
            a["status"] = "cancelled"
            memory.add_message(conn, a["conversation_id"], "system", f"[cancelled {action_id}]")
        return {"trace_id": memory.new_trace_id(), "answer_type": "answered", "language": lang,
                "answer": i18n.t("action_cancelled", lang), "action": actions.to_pending(a).model_dump()}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...), metadata: str = Form(...),
                 _admin: Optional[dict] = Depends(auth.admin_or_open)) -> dict[str, Any]:
    try:
        meta = kb_ingest.SourceMeta(**json.loads(metadata))
    except Exception as e:
        raise HTTPException(422, f"invalid metadata: {e}")
    raw = (await file.read()).decode("utf-8-sig")
    kind = "json" if (file.filename or "").lower().endswith(".json") or meta.doc_type == "grievance" else "md"
    path = config.INGEST_DIR / f"{meta.source_id}.{'json' if kind == 'json' else 'md'}"
    path.write_text(raw, encoding="utf-8")
    meta.file = str(path.relative_to(config.DATA_DIR)) if config.DATA_DIR in path.parents else str(path)
    try:
        return kb_ingest.ingest(meta, raw, kind)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health() -> dict[str, Any]:
    comps: dict[str, Any] = {"api": {"ok": True}}
    try:
        with db.get_conn() as conn:
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("schemes", "eligibility_rules", "citizens", "sources", "service_centres")}
        comps["sqlite"] = {"ok": counts["schemes"] > 0, **counts}
    except Exception as e:
        comps["sqlite"] = {"ok": False, "error": str(e)}
    n = vs.count()
    comps["vector_store"] = {"ok": n > 0, "chunks": n, "embedding_model": config.EMBEDDING_MODEL}
    comps["llm"] = llm.health()
    core_ok = all(comps[k]["ok"] for k in ("api", "sqlite", "vector_store"))
    status = "ok" if core_ok and comps["llm"]["ok"] else "degraded" if core_ok else "down"
    return {"status": status, "components": comps}


@app.get("/conversations")
def conversations(citizen_id: Optional[str] = Query(default=None), user: dict = Depends(auth.require_user)
                  ) -> list[dict[str, Any]]:
    """Past conversations: a user sees only their own; an admin sees everyone's (optionally one citizen's)."""
    if user["role"] != "admin":
        citizen_id = user["citizen_id"]
    with db.get_conn() as conn:
        return memory.list_conversations(conn, citizen_id)


@app.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, user: dict = Depends(auth.require_user)) -> dict[str, Any]:
    with db.get_conn() as conn:
        c = memory.get_conversation(conn, conversation_id)
    if not c:
        raise HTTPException(404, "conversation not found")
    if user["role"] != "admin" and c["citizen_id"] != user["citizen_id"]:
        raise HTTPException(404, "conversation not found")  # do not reveal that it exists
    return c


@app.get("/referrals/{referral_id}")
def get_referral(referral_id: str, user: Optional[dict] = Depends(auth.current_user)) -> dict[str, Any]:
    with db.get_conn() as conn:
        r = db.row(conn, "SELECT * FROM referrals WHERE referral_id=?", (referral_id,))
    if not r or not auth.can_read_owned(user, r["citizen_id"]):
        raise HTTPException(404, "referral not found")
    r["bundle"] = json.loads(r.pop("bundle_json") or "{}")
    return r


@app.get("/audit/{trace_id}")
def audit(trace_id: str, user: Optional[dict] = Depends(auth.current_user)) -> dict[str, Any]:
    with db.get_conn() as conn:
        rec = memory.get_audit(conn, trace_id)
    if not rec or not auth.can_read_owned(user, rec.get("citizen_id")):
        raise HTTPException(404, "audit record not found")
    return rec


REGISTER_FIELDS = ["source_id", "doc_type", "title", "language", "authority_level", "scheme_id", "last_updated",
                   "effective_from", "valid_until", "supersedes", "provenance", "synthetic"]


@app.get("/sources")
def sources() -> list[dict[str, Any]]:
    with db.get_conn() as conn:
        return db.rows(conn, f"SELECT {', '.join(REGISTER_FIELDS)}, contains_instructions, ingested_at FROM sources "
                             "ORDER BY doc_type, source_id")


@app.get("/sources/{source_id}")
def source(source_id: str) -> dict[str, Any]:
    with db.get_conn() as conn:
        r = db.row(conn, "SELECT * FROM sources WHERE source_id=?", (source_id,))
    if not r:
        raise HTTPException(404, "source not found")
    if r["doc_type"] == "grievance":
        try:
            r["content"] = json.dumps(json.loads(r["content"]), ensure_ascii=False, indent=2)
        except Exception:
            pass
    return r


# ------------------------------------------------------------------ UI helpers
@app.get("/schemes")
def schemes(as_of_date: Optional[str] = None) -> list[dict[str, Any]]:
    as_of = as_of_date or tools.now_ist().date().isoformat()
    out = []
    with db.get_conn() as conn:
        for s in tools.list_schemes(conn):
            st = tools.scheme_status(conn, s, as_of)
            notes = []
            for n in st["notes"]:
                if n["type"] == "deadline_extended":
                    notes.append(f"Last date extended from {n['old']} to {n['new']} by {n['source_id']}")
                elif n["type"] == "closed_by_circular":
                    notes.append(f"Closed for new applications from {n['effective_from']} ({n['source_id']})")
                elif n["type"] == "deadline_passed":
                    notes.append(f"Last date {n['date']} has passed")
            for u in st["upcoming"]:
                notes.append(f"Upcoming change on {u['effective_from']} ({u['source_id']})")
            docs = [{k: d[k] for k in ("document_name", "mandatory", "notes")} for d in tools.get_required_documents(conn, s["scheme_id"])]
            out.append({**s, "status": st["status"], "apply_until": st["apply_until"], "days_left": st["days_left"],
                        "notes": notes, "documents": docs})
    return out


@app.get("/citizens/demo")
def citizens_demo(_admin: dict = Depends(auth.require_admin)) -> list[dict[str, Any]]:
    """Admin only: IDs and non-identifying fields of every citizen."""
    with db.get_conn() as conn:
        return db.rows(conn, "SELECT citizen_id, district, residence_type, preferred_language, consent_given "
                             "FROM citizens ORDER BY citizen_id")


@app.get("/admin/users")
def admin_users(_admin: dict = Depends(auth.require_admin)) -> list[dict[str, Any]]:
    """Admin only: every citizen (a potential user) with account and conversation counts."""
    with db.get_conn() as conn:
        return db.rows(conn, """
            SELECT c.citizen_id, c.district, c.residence_type, c.preferred_language, c.consent_given,
                   CASE WHEN u.username IS NULL THEN 0 ELSE 1 END AS has_signed_in,
                   (SELECT COUNT(*) FROM conversations v WHERE v.citizen_id = c.citizen_id) AS conversations,
                   (SELECT MAX(updated_at) FROM conversations v WHERE v.citizen_id = c.citizen_id) AS last_active
            FROM citizens c LEFT JOIN users u ON u.citizen_id = c.citizen_id
            ORDER BY last_active IS NULL, last_active DESC, c.citizen_id""")


@app.post("/admin/load")
async def admin_load(files: list[UploadFile] = File(...),
                     _admin: Optional[dict] = Depends(auth.admin_or_open)) -> dict[str, Any]:
    report: dict[str, Any] = {"loaded": {}, "errors": []}
    order = list(loader.TABLES)
    items = []
    for f in files:
        table = loader.table_for_filename(f.filename or "")
        if not table:
            report["errors"].append(f"{f.filename}: no matching table (name files like citizens.csv)")
            continue
        items.append((order.index(table), table, f.filename, (await f.read()).decode("utf-8-sig")))
    with db.get_conn() as conn:
        for _, table, name, text in sorted(items):
            n, errs = loader.load_csv_text(conn, table, text)
            report["loaded"][table] = report["loaded"].get(table, 0) + n
            report["errors"] += [f"{name}: {e}" for e in errs]
    return report


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "SchemeSathi API", "docs": "/docs", "health": "/health",
            "note": "Fictional state of Mitrapur Pradesh. Not real advice."}
