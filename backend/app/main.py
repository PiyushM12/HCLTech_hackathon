"""FastAPI app: the API contract in Section 6 of the participant guide, plus small read-only
helpers the UI uses (/schemes, /sources/{id}, /citizens/demo) and an admin CSV loader."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth, config, db, i18n, loader, memory, tools
from .agents import actions
from .graph import run_ask
from .kb import ingest as kb_ingest
from .kb import vectorstore as vs
from .llm import llm
from .models import AskRequest, AskResponse, EligibilityRequest, RecommendationRequest


log = logging.getLogger("schemesathi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    vs.get_embedder()  # load the shared model before indexing individual sources
    report = kb_ingest.build_kb()
    log.info("knowledge base ready: %s", {k: v for k, v in report.items() if k != "seed"})
    yield


app = FastAPI(title="SchemeSathi API", version="1.0.0", lifespan=lifespan,
              description="Multilingual citizen scheme navigator for the fictional state of Mitrapur Pradesh. "
                          "All schemes, amounts and offices are fictional; nothing here is real advice.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path == "/auth/login":
        return JSONResponse({"detail": "Choose a role and enter a valid username and password."}, status_code=422)
    if request.url.path == "/auth/register":
        return JSONResponse({"detail": "Enter a valid username and a password of 12–128 characters."}, status_code=422)
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def private_response_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in {"/ask", "/conversations", "/schemes/recommendations"} or request.url.path.startswith(
        ("/auth/", "/conversations/", "/referrals/", "/audit/", "/actions/", "/citizens/", "/admin/")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------------ core contract
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, session: auth.Session = Depends(auth.chat_session)) -> AskResponse:
    if session.role == "admin":
        raise HTTPException(403, "Sign in as a user to ask about schemes.")
    return run_ask(req, session.owner_id)


@app.post("/eligibility")
def eligibility(req: EligibilityRequest) -> dict[str, Any]:
    as_of = req.as_of_date or tools.now_ist().date().isoformat()
    with db.get_conn() as conn:
        res = tools.check_eligibility(conn, req.attributes, req.scheme_ids, as_of)
    return {"as_of_date": as_of, "results": [r.model_dump() for r in res]}


def _load_action(conn, action_id: str, citizen_id: str) -> dict[str, Any]:
    a = db.row(conn, "SELECT * FROM actions WHERE action_id=?", (action_id,))
    if not a:
        raise HTTPException(404, "action not found")
    if a["citizen_id"] != citizen_id:
        raise HTTPException(403, "only the citizen who owns this action can confirm or cancel it")
    return a


@app.post("/actions/{action_id}/confirm")
def confirm(action_id: str, session: auth.Session = Depends(auth.require_user)) -> dict[str, Any]:
    cid = session.owner_id
    trace_id = memory.new_trace_id()
    with db.get_conn() as conn:
        # Lock before reading the proposal so simultaneous confirms cannot both execute it.
        conn.execute("BEGIN IMMEDIATE")
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
        conn.execute("UPDATE conversations SET updated_at=datetime('now') WHERE conversation_id=?", (a["conversation_id"],))
        memory.save_audit(conn, trace_id, a["conversation_id"], {
            "trace_id": trace_id, "conversation_id": a["conversation_id"], "citizen_id": cid,
            "answer_type": "action_completed", "reply_language": lang, "route": ["confirm", "execute", "verify"],
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
def cancel(action_id: str, session: auth.Session = Depends(auth.require_user)) -> dict[str, Any]:
    cid = session.owner_id
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        a = _load_action(conn, action_id, cid)
        lang = a.get("language") or "en"
        if a["status"] == "executed":
            raise HTTPException(409, "this action was already executed; ask to cancel the booking instead")
        trace_id = memory.new_trace_id()
        message = i18n.t("action_cancelled", lang)
        if a["status"] != "cancelled":
            conn.execute("UPDATE actions SET status='cancelled' WHERE action_id=?", (action_id,))
            a["status"] = "cancelled"
            memory.add_message(conn, a["conversation_id"], "system", f"[cancelled {action_id}]")
            memory.add_message(conn, a["conversation_id"], "assistant", message, trace_id, "answered", ["cancel"])
            memory.save_audit(conn, trace_id, a["conversation_id"], {
                "trace_id": trace_id, "conversation_id": a["conversation_id"], "citizen_id": cid,
                "answer_type": "answered", "reply_language": lang, "route": ["cancel"],
            })
            conn.execute("UPDATE conversations SET updated_at=datetime('now') WHERE conversation_id=?", (a["conversation_id"],))
        return {"trace_id": trace_id, "answer_type": "answered", "language": lang,
                "answer": message, "action": actions.to_pending(a).model_dump()}


@app.post("/ingest", dependencies=[Depends(auth.require_admin)])
async def ingest(file: UploadFile = File(...), metadata: str = Form(...)) -> dict[str, Any]:
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


@app.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, session: auth.Session | None = Depends(auth.get_session)) -> dict[str, Any]:
    with db.get_conn() as conn:
        owner = db.row(conn, "SELECT citizen_id FROM conversations WHERE conversation_id=?", (conversation_id,))
        if not session or not owner or not session.can_read(owner["citizen_id"]):
            raise HTTPException(404, "conversation not found")
        c = memory.get_conversation(conn, conversation_id)
    if not c:
        raise HTTPException(404, "conversation not found")
    return c


@app.get("/conversations")
def conversations(session: auth.Session = Depends(auth.require_user)) -> list[dict[str, Any]]:
    with db.get_conn() as conn:
        return memory.list_conversations(conn, session.owner_id)


@app.get("/referrals/{referral_id}")
def get_referral(referral_id: str, session: auth.Session | None = Depends(auth.get_session)) -> dict[str, Any]:
    with db.get_conn() as conn:
        r = db.row(conn, "SELECT * FROM referrals WHERE referral_id=?", (referral_id,))
    if not session or not r or not session.can_read(r["citizen_id"]):
        raise HTTPException(404, "referral not found")
    r["bundle"] = json.loads(r.pop("bundle_json") or "{}")
    return r


@app.get("/audit/{trace_id}")
def audit(trace_id: str, session: auth.Session | None = Depends(auth.get_session)) -> dict[str, Any]:
    with db.get_conn() as conn:
        owner = db.row(conn, """SELECT c.citizen_id FROM audit a JOIN conversations c
            ON c.conversation_id=a.conversation_id WHERE a.trace_id=?""", (trace_id,))
        if not session or not owner or not session.can_read(owner["citizen_id"]):
            raise HTTPException(404, "audit record not found")
        rec = memory.get_audit(conn, trace_id)
    if not rec:
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
    with db.get_conn() as conn:
        return _scheme_catalog(conn, as_of)


@app.post("/schemes/recommendations")
def recommended_schemes(req: RecommendationRequest, session: auth.Session = Depends(auth.require_user)) -> list[dict[str, Any]]:
    as_of = req.as_of_date or tools.now_ist().date().isoformat()
    with db.get_conn() as conn:
        attributes = req.attributes
        if attributes is None:
            attributes = tools.lookup_citizen(conn, session.owner_id, as_of).get("attributes", {})
            if req.conversation_id:
                saved = db.row(conn, "SELECT state_json FROM conversations WHERE conversation_id=? AND citizen_id=?",
                               (req.conversation_id, session.owner_id))
                if not saved:
                    raise HTTPException(404, "conversation not found")
                context = json.loads(saved["state_json"] or "{}")
                if context.get("subject") == "self":
                    attributes.update(context.get("attributes", {}))
        verdicts = {v.scheme_id: v.verdict for v in tools.check_eligibility(conn, attributes, None, as_of)
                    if v.verdict in tools.RECOMMENDED_VERDICTS}
        return [{**s, "verdict": verdicts[s["scheme_id"]]} for s in _scheme_catalog(conn, as_of, verdicts)]


def _scheme_catalog(conn, as_of: str, only: dict[str, str] | None = None) -> list[dict[str, Any]]:
    out = []
    for s in tools.list_schemes(conn):
        if only is not None and s["scheme_id"] not in only:
            continue
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


@app.get("/citizens/demo", dependencies=[Depends(auth.require_admin)])
def citizens_demo() -> list[dict[str, Any]]:
    """List citizen IDs and basic fields for account administration."""
    with db.get_conn() as conn:
        return db.rows(conn, "SELECT citizen_id, district, residence_type, preferred_language, consent_given "
                             "FROM citizens ORDER BY citizen_id")


@app.post("/admin/load", dependencies=[Depends(auth.require_admin)])
async def admin_load(files: list[UploadFile] = File(...)) -> dict[str, Any]:
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
