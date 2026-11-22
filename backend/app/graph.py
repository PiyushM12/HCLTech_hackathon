"""Orchestration (LangGraph). One supervisor graph with deterministic routing.

Why one graph and not a crowd of LLM agents: every routing decision here is a policy that
must be predictable and testable (Annex A), so routing is code. The "agents" are nodes
with one job each; only two of them may call the LLM (classifier, free-text composer).

    guard -> classify -> route -+-> respond (refusal / out of scope / greeting / language)
                                +-> eligibility --+
                                +-> knowledge ----+-> critic -> (revise -> critic) -> policy -> [referral] -> finalize
                                +-> action -------+
                                +-> referral (grievance / fraud)
                                reterval  -----------------------------------------> finalize
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import db, i18n, memory, tools
from .agents import actions, classifier, composer, critic, evidence, referral
from .i18n import t
from .kb import vectorstore as vs
from .llm import LLMStats, llm
from .models import AskRequest, AskResponse, Citation, IntentOut, Question, SchemeVerdict, ToolCall
from .nlp import extract, pii
from .rules.engine import SENSITIVE

PERSON_ATTRS = {"age", "gender", "occupation", "is_disabled", "disability_percent"}


class S(TypedDict, total=False):
    conn: Any
    req: AskRequest
    citizen_id: str
    as_of: str
    trace_id: str
    t0: float
    timings: dict
    route: list
    stats: LLMStats
    conversation_id: str
    conv: dict
    is_new: bool
    citizen: dict
    message: str
    message_redacted: str
    pii_types: list
    intent: IntentOut
    cls_debug: dict
    lang: str
    attrs: dict
    attr_sources: dict
    focus: list
    verdicts: list
    statuses: dict
    questions: list
    retrieved: list
    tool_calls: list
    tool_failures: list
    draft: dict
    evidence: list
    critic: Any
    revisions: int
    answer_type: str
    answer: str
    pending_action: Any
    referral_reasons: list
    referral_id: str
    referral: dict
    conflicts: list
    respond_kind: str
    overdue: list
    apps: list
    state_updates: dict
    citations_final: list
    mode: str


def _timed(name: str):
    def deco(fn):
        def wrapper(state: S) -> dict:
            t0 = time.perf_counter()
            out = fn(state) or {}
            timings = dict(state.get("timings") or {})
            timings[name] = round((time.perf_counter() - t0) * 1000, 1)
            out["timings"] = timings
            out["route"] = list(state.get("route") or []) + [name]
            return out
        return wrapper
    return deco


def _tool(state: S, tool: str, inp: dict, output: Any, ok: bool = True, ms: float = 0.0) -> list:
    calls = list(state.get("tool_calls") or [])
    calls.append(ToolCall(tool=tool, input=pii.redact_obj(inp), output=output, ok=ok, latency_ms=round(ms, 1)))
    return calls


def _schemes(conn) -> dict[str, dict]:
    return {s["scheme_id"]: s for s in tools.list_schemes(conn)}


# ------------------------------------------------------------------ nodes
@_timed("guard")
def guard(state: S) -> dict:
    conn, req = state["conn"], state["req"]
    cid, conv, is_new = memory.load_conversation(conn, req.conversation_id, state["citizen_id"])
    citizen = tools.lookup_citizen(conn, state["citizen_id"], state["as_of"])
    redacted, found = pii.redact(req.message)
    calls = _tool(state, "lookup_citizen", {"citizen_id": state["citizen_id"]},
                  {k: v for k, v in citizen.items() if not k.startswith("_") and k != "attributes"}
                  | {"profile_used": bool(citizen.get("attributes"))})
    return {"conversation_id": cid, "conv": conv, "is_new": is_new, "citizen": citizen, "message": req.message,
            "message_redacted": redacted, "pii_types": found, "tool_calls": calls}


@_timed("classify")
def classify(state: S) -> dict:
    conn = state["conn"]
    intent, debug = classifier.classify(state["message"], conv=state["conv"], schemes=tools.list_schemes(conn),
                                        citizen_id=state["citizen_id"], stats=state["stats"])
    req = state["req"]
    if req.language:
        lang = req.language
    elif intent.language in {"hi", "en", "kn", "ta", "hinglish"}:
        lang = intent.language
    else:
        lang = "en"
    if "language_ambiguous" in intent.flags and not req.language:
        lang = state["conv"].get("reply_language") or "en"
    return {"intent": intent, "cls_debug": debug, "lang": lang}


def route(state: S) -> str:
    it: IntentOut = state["intent"]
    f = set(it.flags)
    if "language_ambiguous" in f and not state["req"].language and not state["conv"].get("reply_language"):
        return "respond"
    if {"other_person_data", "secret_request", "typed_confirmation", "greeting"} & f:
        return "respond"
    if "prompt_injection" in f and not it.attributes_mentioned and not it.scheme_ids:
        return "respond"
    if it.type == "out_of_scope":
        return "respond"
    if it.type in {"fraud_report", "grievance"}:
        return "referral"
    if it.type in {"service_visit", "application_draft"} or (it.type == "status_deadline" and "reminder" in f):
        return "action"
    if it.type in {"discovery", "eligibility_check"} and not ({"scheme_info", "unknown_scheme", "general_question"} & f):
        return "eligibility"
    return "knowledge"


@_timed("respond")
def respond(state: S) -> dict:
    it, lang = state["intent"], state["lang"]
    f = set(it.flags)
    if "language_ambiguous" in f and not state["req"].language:
        return {"answer_type": "clarification_needed", "answer": t("lang_ask", "en"), "respond_kind": "lang_ask"}
    if "other_person_data" in f:
        return {"answer_type": "refused", "answer": t("refused_other", lang), "respond_kind": "refused_other"}
    if "secret_request" in f:
        return {"answer_type": "refused", "answer": t("refused_secret", lang), "respond_kind": "refused_secret"}
    if "typed_confirmation" in f:
        row = db.row(state["conn"], "SELECT * FROM actions WHERE action_id=?", (state["conv"].get("last_action_id"),))
        pa = actions.to_pending(row) if row and row["status"] == "pending" else None
        return {"answer_type": "confirmation_needed" if pa else "answered", "answer": t("confirm_typed", lang),
                "pending_action": pa, "respond_kind": "confirm_typed"}
    if "greeting" in f:
        return {"answer_type": "clarification_needed", "answer": t("greeting", lang), "respond_kind": "greeting"}
    if "prompt_injection" in f:
        return {"answer_type": "clarification_needed", "answer": t("injection_note", lang), "respond_kind": "injection"}
    return {"answer_type": "out_of_scope", "answer": t("out_of_scope", lang), "respond_kind": "out_of_scope"}


def _merged_attributes(state: S) -> tuple[dict, dict, dict]:
    conv, it, citizen = state["conv"], state["intent"], state["citizen"]
    subject = it.subject if it.attributes_mentioned or it.subject == "other" else conv.get("subject", "self")
    if subject == "self" and conv.get("subject") == "other" and not extract.signals(state["message"])["self_marker"]:
        subject = "other"  # a bare follow-up answer ("income 1.2 lakh") is still about the same applicant
    base = dict(conv.get("attributes") or {})
    if conv.get("subject") and subject != conv.get("subject"):
        base = {k: v for k, v in base.items() if k not in PERSON_ATTRS}  # new applicant: forget person facts
    sources = {k: "conversation" for k in base}
    prof = citizen.get("attributes") or {}
    for k, v in prof.items():
        if k in base:
            continue
        if subject == "self" or k in tools.HOUSEHOLD_ATTRS:
            base[k] = v
            sources[k] = "profile"
    for k, v in it.attributes_mentioned.items():
        base[k] = v
        sources[k] = "citizen_said"
    upd = {"subject": subject, "attributes": {k: v for k, v in base.items() if sources.get(k) != "profile"}}
    return base, sources, upd


@_timed("eligibility")
def eligibility(state: S) -> dict:
    conn, it, lang, as_of = state["conn"], state["intent"], state["lang"], state["as_of"]
    attrs, sources, upd = _merged_attributes(state)
    schemes = _schemes(conn)
    t0 = time.perf_counter()
    verdicts = tools.check_eligibility(conn, attrs, None, as_of)
    statuses = {v.scheme_id: tools.scheme_status(conn, schemes.get(v.scheme_id) or tools.scheme_row(conn, v.scheme_id), as_of)
                for v in verdicts}
    for sid in schemes:
        statuses.setdefault(sid, tools.scheme_status(conn, schemes[sid], as_of))
    calls = _tool(state, "check_eligibility", {"attributes": attrs, "scheme_ids": it.scheme_ids or "ALL", "as_of": as_of},
                  [{"scheme_id": v.scheme_id, "verdict": v.verdict,
                    "rules": [{"rule_id": r.rule_id, "attribute": r.attribute, "result": r.result} for r in v.rules],
                    "unknown": v.unknown} for v in verdicts], ms=(time.perf_counter() - t0) * 1000)
    mode = "eligibility_check" if (it.type == "eligibility_check" and it.scheme_ids) else "discovery"
    focus_ids = it.scheme_ids if mode == "eligibility_check" else [
        v.scheme_id for v in verdicts if v.verdict in tools.RECOMMENDED_VERDICTS
        and statuses[v.scheme_id]["status"] in {"open", "upcoming"}]
    focus = [v for v in verdicts if v.scheme_id in focus_ids]
    conv = state["conv"]
    asked = set(conv.get("asked") or [])
    max_q = int(tools.policy(conn, "max_questions_per_turn", as_of))
    questions: list[Question] = []
    need: dict[str, list[str]] = {}
    for v in focus:
        if v.verdict != "need_more_information" or statuses[v.scheme_id]["status"] == "closed":
            continue
        if mode == "discovery" and statuses[v.scheme_id]["status"] != "open":
            continue
        if mode == "discovery" and any(r.result == "unknown" and r.attribute in SENSITIVE and not r.rule_group
                                       for r in v.rules):
            continue  # e.g. a disability scheme for someone who never mentioned a disability
        for a in v.unknown:
            if a in asked:
                continue
            if mode == "discovery" and a in SENSITIVE:
                continue  # R5: sensitive attributes only when the scheme in focus needs them
            need.setdefault(a, []).append(v.scheme_id)
    rounds = conv.get("question_rounds", 0)
    allow = mode == "eligibility_check" or rounds < 2
    if need and allow:
        ranked = sorted(need, key=lambda a: (-len(need[a]), composer.ATTR_ORDER.index(a) if a in composer.ATTR_ORDER else 99))
        for a in ranked[:max_q]:
            names = ", ".join(i18n.scheme_name(schemes.get(s, {"name_en": s}), lang, both=False) for s in need[a][:3])
            questions.append(Question(attribute=a, text=t(f"q_{a}", lang), reason=t("why_ask", lang, schemes=names)))
    upd.update({"focus_schemes": focus_ids if mode == "eligibility_check" else [], "last_intent": it.type})
    if questions:
        lines = [t("clar_intro", lang)]
        fl = composer.facts_line(attrs, lang)
        if fl:
            lines.insert(0, fl)
        for q in questions:
            lines.append(f"- {q.text} ({q.reason})")
        upd.update({"pending_question_attrs": [q.attribute for q in questions], "pending_intent": it.type,
                    "asked": sorted(asked | {q.attribute for q in questions}), "question_rounds": rounds + 1,
                    "questions_total": conv.get("questions_total", 0) + len(questions)})
        return {"attrs": attrs, "attr_sources": sources, "verdicts": verdicts, "statuses": statuses, "focus": focus_ids,
                "questions": questions, "tool_calls": calls, "answer_type": "clarification_needed",
                "answer": "\n".join(lines), "state_updates": upd,
                "draft": {"text": "\n".join(lines), "cites": [], "kind": "clarification", "used_hits": []}}
    upd.update({"pending_question_attrs": [], "pending_intent": None})
    docs = {v.scheme_id: tools.get_required_documents(conn, v.scheme_id) for v in focus if v.verdict == "appears_eligible"}
    if mode == "eligibility_check":
        alternatives = [v for v in verdicts if v.verdict == "appears_eligible" and v.scheme_id not in focus_ids
                        and statuses[v.scheme_id]["status"] == "open"]
        partial = sorted({a for v in focus if v.verdict == "need_more_information"
                          and statuses[v.scheme_id]["status"] != "closed" for a in v.unknown})
        draft = composer.compose_eligibility(lang=lang, focus=focus, schemes=schemes, docs=docs, statuses=statuses,
                                             attrs=attrs, alternatives=alternatives, partial_attrs=partial)
        for sid, dl in docs.items():
            calls = calls + [ToolCall(tool="get_required_documents", input={"scheme_id": sid},
                                      output=[{"document_name": d["document_name"], "mandatory": d["mandatory"]} for d in dl])]
    else:
        draft = composer.compose_discovery(lang=lang, verdicts=focus, schemes=schemes, statuses=statuses, attrs=attrs)
    conflicts = [c for v in focus for c in v.conflicts]
    # per-scheme facts are added by the critic's evidence builder; only computed values go here
    return {"attrs": attrs, "attr_sources": sources, "verdicts": verdicts, "statuses": statuses, "focus": focus_ids,
            "tool_calls": calls, "draft": draft, "conflicts": conflicts, "state_updates": upd,
            "mode": mode}


def _scheme_examples(conn, lang: str) -> str:
    return ", ".join(i18n.scheme_name(s, lang, both=False) for s in tools.list_schemes(conn)[:4])


@_timed("knowledge")
def knowledge(state: S) -> dict:
    conn, it, lang, as_of = state["conn"], state["intent"], state["lang"], state["as_of"]
    schemes = _schemes(conn)
    f = set(it.flags)
    upd = {"last_intent": it.type, "pending_question_attrs": [], "pending_intent": None}
    calls = list(state.get("tool_calls") or [])
    evidence: list[str] = []
    ids = [s for s in it.scheme_ids if s in schemes or tools.scheme_row(conn, s)]
    if ids:
        upd["focus_schemes"] = ids
    clar = None
    if it.type == "documents":
        if not ids:
            clar = t("ask_scheme", lang, examples=_scheme_examples(conn, lang))
            upd.update({"pending_intent": "documents"})
        else:
            items = []
            for sid in ids[:2]:
                docs = tools.get_required_documents(conn, sid)
                calls.append(ToolCall(tool="get_required_documents", input={"scheme_id": sid},
                                      output=[{"document_name": d["document_name"], "mandatory": d["mandatory"],
                                               "notes": d["notes"]} for d in docs]))
                items.append((schemes.get(sid) or tools.scheme_row(conn, sid), docs))
                evidence.append(json.dumps(docs, ensure_ascii=False))
            draft, newly = composer.compose_documents(lang=lang, items=items, explained=state["conv"].get("terms_explained") or [])
            upd["terms_explained"] = (state["conv"].get("terms_explained") or []) + newly
            return {"draft": draft, "evidence": evidence, "tool_calls": calls, "focus": ids, "state_updates": upd}
    elif it.type == "status_deadline" and "app_status" in f:
        cit = state["citizen"]
        if not cit.get("found"):
            clar = t("need_login", lang)
        elif cit.get("consent_given") != "Y":
            clar = t("need_consent", lang)
        else:
            apps = tools.get_applications(conn, state["citizen_id"])
            calls.append(ToolCall(tool="get_applications", input={"citizen_id": state["citizen_id"]}, output=apps))
            target = int(tools.policy(conn, "application_processing_target_days", as_of))
            overdue = [a for a in apps if a["status"] == "submitted" and a["status_updated_on"] and
                       (date.fromisoformat(as_of) - date.fromisoformat(a["status_updated_on"])).days > target]
            draft = composer.compose_app_status(lang=lang, apps=apps, schemes=schemes, overdue=overdue, target_days=target)
            evidence += [json.dumps(apps, ensure_ascii=False), f"target {target} days"]
            return {"draft": draft, "evidence": evidence, "tool_calls": calls, "apps": apps, "overdue": overdue,
                    "state_updates": upd}
    elif it.type == "status_deadline":
        targets = ids or [s for s, row in schemes.items() if row.get("apply_until")]
        items = []
        for sid in targets[:4]:
            g = tools.get_scheme(conn, sid, as_of)
            if g:
                calls.append(ToolCall(tool="get_scheme", input={"scheme_id": sid, "as_of": as_of}, output=g["effective"]))
                items.append((g, g["effective"]))
                evidence.append(json.dumps(g, ensure_ascii=False, default=str))
        return {"draft": composer.compose_status(lang=lang, items=items), "evidence": evidence, "tool_calls": calls,
                "focus": targets[:4], "state_updates": upd}
    elif "scheme_info" in f and ids:
        sid = ids[0]
        g = tools.get_scheme(conn, sid, as_of)
        from .rules import engine
        rules = engine.rules_in_force(conn, sid, as_of)
        v = tools.check_eligibility(conn, {}, [sid], as_of)[0]
        ul, uc = composer.upcoming_rule_lines(v, lang)
        calls.append(ToolCall(tool="get_scheme", input={"scheme_id": sid, "as_of": as_of}, output=g["effective"]))
        draft = composer.compose_scheme_info(lang=lang, scheme=g, status=g["effective"], rules=rules, upcoming=ul)
        draft["cites"] += uc
        evidence += [json.dumps(g, ensure_ascii=False, default=str), json.dumps(rules, ensure_ascii=False),
                     json.dumps(v.upcoming_changes, ensure_ascii=False)]
        return {"draft": draft, "evidence": evidence, "tool_calls": calls, "focus": [sid], "state_updates": upd}
    if clar:
        return {"answer_type": "clarification_needed", "answer": clar, "tool_calls": calls, "state_updates": upd,
                "draft": {"text": clar, "cites": [], "kind": "clarification", "used_hits": []},
                "questions": [Question(attribute="scheme", text=clar, reason="")]}
    # free-text question: retrieval-augmented
    return {"draft": None, "tool_calls": calls, "focus": ids, "state_updates": upd}


def _retrieve(state: S, query: str, scheme_ids: list[str]) -> tuple[list[dict], list[str]]:
    failures = []
    try:
        k = int(tools.policy(state["conn"], "retrieval_top_k", state["as_of"]))
        hits = vs.search(query, k=k, scheme_ids=scheme_ids or None, as_of=state["as_of"])
    except Exception as e:  # tool failure is a referral reason (Annex A.4)
        hits, failures = [], [f"retrieval: {e}"]
    return hits, failures


@_timed("retrieve")
def retrieve(state: S) -> dict:
    """Retrieve top-k passages across languages, then pin the exact sections the draft cites."""
    conn, lang, it = state["conn"], state["lang"], state["intent"]
    draft = state.get("draft")
    hits, failures = _retrieve(state, state["message"], state.get("focus") or it.scheme_ids)
    if draft is None:  # free-text path: compose from passages
        f = set(it.flags)
        words = extract.content_words(state["message"])
        top_text = " ".join(h["text"].lower() for h in hits[:4])
        coverage = (sum(1 for w in words if w in top_text) / len(words)) if words else 1.0
        if ("unknown_scheme" in f or "general_question" in f) and not it.scheme_ids and coverage < 0.5:
            draft = {"text": "", "cites": [], "kind": "not_found", "used_hits": []}
        else:
            draft = composer.compose_general(lang=lang, question=state["message"], hits=hits, stats=state["stats"],
                                             safe=False, use_llm=not llm.mock)
            if not draft["text"]:
                draft = {"text": "", "cites": [], "kind": "not_found", "used_hits": []}
    pinned = []
    for sid, sec in draft.get("cites", []):
        if not sid:
            continue
        if any(h["source_id"] == sid and (not sec or h["section"].split(" ")[0] == sec.split(" ")[0]) for h in hits + pinned):
            continue
        p = None
        try:
            # a citation without a section points at the operative clause (section 2 of a circular)
            p = vs.get_section(sid, sec or "2")
            if p is None and not sec:
                p = vs.get_section(sid, "1")
        except Exception as e:
            failures.append(f"pin {sid}: {e}")
        if p:
            pinned.append(p)
    calls = _tool(state, "search_knowledge_base", {"query": state["message_redacted"], "scheme_ids": state.get("focus") or []},
                  [{"source_id": h["source_id"], "section": h["section"], "score": h["score"],
                    "language": h["meta"].get("language"), "authority": h["meta"].get("authority_level")} for h in hits],
                  ok=not failures)
    return {"retrieved": hits + pinned, "draft": draft, "tool_calls": calls,
            "tool_failures": list(state.get("tool_failures") or []) + failures}


@_timed("action")
def action(state: S) -> dict:
    conn, it, lang, as_of = state["conn"], state["intent"], state["lang"], state["as_of"]
    citizen, cid = state["citizen"], state["citizen_id"]
    attrs, sources, upd = _merged_attributes(state)
    upd["last_intent"] = it.type
    f = set(it.flags)
    schemes = _schemes(conn)
    calls = list(state.get("tool_calls") or [])
    conv_id = state["conversation_id"]
    sid = (it.scheme_ids or state["conv"].get("focus_schemes") or [None])[0]
    res: actions.PlanResult
    if it.type == "service_visit" and "cancel_appointment" in f:
        res = actions.plan_cancel(conn, citizen=citizen, citizen_id=cid, lang=lang, as_of=as_of, conversation_id=conv_id)
    elif it.type == "service_visit" and "centre_info" in f:
        district = attrs.get("district")
        if not district:
            res = actions.PlanResult(kind="clarify", answer=t("q_district", lang), tool_calls=[], pending_attrs=["district"])
        else:
            centres = tools.find_service_centres(conn, district, lang)
            calls.append(ToolCall(tool="find_service_centres", input={"district": district}, output=centres))
            d = composer.compose_centres(lang=lang, district=district, centres=centres)
            res = actions.PlanResult(kind="info", answer=d["text"], tool_calls=[], evidence=[json.dumps(centres, ensure_ascii=False)])
    elif it.type == "service_visit":
        res = actions.plan_booking(conn, citizen=citizen, citizen_id=cid, message=state["message"], attrs=attrs, lang=lang,
                                   as_of=as_of, conversation_id=conv_id, wants_reminder="reminder" in f)
    elif not citizen.get("found"):
        res = actions.PlanResult(kind="clarify", answer=t("need_login", lang), tool_calls=[])
    elif not sid:
        res = actions.PlanResult(kind="clarify", answer=t("ask_scheme", lang, examples=_scheme_examples(conn, lang)),
                                 tool_calls=[])
        upd["pending_intent"] = it.type
    elif it.type == "status_deadline":  # deadline reminder
        g = tools.get_scheme(conn, sid, as_of)
        res = actions.plan_reminder(conn, citizen=citizen, citizen_id=cid, scheme=g, status=g["effective"], lang=lang,
                                    as_of=as_of, conversation_id=conv_id)
    else:  # application draft
        if citizen.get("consent_given") != "Y":
            res = actions.PlanResult(kind="clarify", answer=t("need_consent", lang), tool_calls=[])
        else:
            scheme = schemes.get(sid) or tools.scheme_row(conn, sid)
            v = tools.check_eligibility(conn, attrs, [sid], as_of)[0]
            docs = tools.get_required_documents(conn, sid)
            apps = tools.get_applications(conn, cid)
            calls += [ToolCall(tool="check_eligibility", input={"scheme_ids": [sid]}, output={"verdict": v.verdict}),
                      ToolCall(tool="get_applications", input={"citizen_id": cid}, output=apps)]
            res = actions.plan_draft(conn, citizen=citizen, citizen_id=cid, scheme=scheme, verdict=v, docs=docs, apps=apps,
                                     lang=lang, as_of=as_of, conversation_id=conv_id,
                                     extra_attrs={k: v2 for k, v2 in attrs.items() if sources.get(k) == "citizen_said"})
    for c in res.get("tool_calls", []):
        calls.append(ToolCall(**c))
    pa = res.get("pending_action")
    if pa:
        upd["last_action_id"] = pa.action_id
    if res.get("pending_attrs"):
        upd["pending_question_attrs"] = res["pending_attrs"]
        upd["pending_intent"] = it.type
    answer_type = {"proposal": "confirmation_needed", "clarify": "clarification_needed", "info": "answered"}[res["kind"]]
    draft = {"text": res["answer"], "cites": [("POL-APPT-01", "2")] if it.type == "service_visit" and pa else [],
             "kind": "action", "used_hits": []}
    return {"answer_type": answer_type, "draft": draft, "pending_action": pa, "tool_calls": calls, "attrs": attrs,
            "evidence": list(res.get("evidence") or []) + [json.dumps(attrs, ensure_ascii=False)],
            "state_updates": upd, "questions": [Question(**q) for q in res.get("questions", [])]}


@_timed("critic")
def critic_node(state: S) -> dict:
    draft = state.get("draft") or {"text": "", "cites": [], "kind": "none"}
    if draft["kind"] in {"not_found", "clarification"}:
        return {"critic": None}
    ev = evidence.build(state["conn"], state["as_of"], retrieved=state.get("retrieved"),
                        tool_calls=state.get("tool_calls"), extra=state.get("evidence"), attrs=state.get("attrs"),
                        cites=draft.get("cites"))
    th = float(tools.policy(state["conn"], "critic_min_groundedness", state["as_of"]))
    mx = int(tools.policy(state["conn"], "critic_max_revisions", state["as_of"]))
    has_verdict = draft["kind"] == "eligibility" and any(
        v.verdict in {"appears_eligible", "not_eligible"} for v in state.get("verdicts") or []
        if v.scheme_id in (state.get("focus") or []))
    out = critic.review(draft=draft, lang=state["lang"], evidence_authoritative=ev["general"],
                        evidence_historical=ev["historical"], retrieved=state.get("retrieved") or [],
                        answer_kind=draft["kind"], has_verdict=has_verdict, threshold=th,
                        revisions=state.get("revisions", 0), max_revisions=mx, evidence_scoped=ev["scoped"],
                        superseded=ev["superseded"], current=ev["current"], citizen_values=ev["citizen"],
                        schemes=ev["schemes"])
    prev = state.get("critic")
    if prev is not None and state.get("revisions", 0) > 0:
        out.issues = [f"caught before revision: {i}" for i in prev.issues if not i.startswith("caught before")] + out.issues
    return {"critic": out}


def after_critic(state: S) -> str:
    c = state.get("critic")
    if c is not None and c.decision == "revise":
        return "revise"
    return "policy"


@_timed("revise")
def revise(state: S) -> dict:
    """One revision (R7): rebuild the draft from authoritative sources only."""
    draft = dict(state["draft"])
    if draft["kind"].startswith("general"):
        new = composer.compose_general(lang=state["lang"], question=state["message"], hits=state.get("retrieved") or [],
                                       stats=state["stats"], safe=True, use_llm=False)
        draft = new if new["text"] else {"text": "", "cites": [], "kind": "not_found", "used_hits": []}
    else:
        draft["text"] = pii.redact(draft["text"])[0]
        for pat in critic.PROMISE.get(i18n.L(state["lang"]), []):
            import re
            draft["text"] = re.sub(pat, "", draft["text"], flags=re.I)
    return {"draft": draft, "revisions": state.get("revisions", 0) + 1}


@_timed("policy")
def policy_node(state: S) -> dict:
    """Referral policy (Annex A.4) over classifier + critic + tool outputs."""
    it = state["intent"]
    draft = state.get("draft") or {}
    answer_type = state.get("answer_type")
    if not answer_type:
        answer_type = "not_found" if draft.get("kind") == "not_found" else "answered"
    answer = state.get("answer") or (t("not_found", state["lang"]) if draft.get("kind") == "not_found" else draft.get("text", ""))
    if answer_type == "clarification_needed" and draft.get("kind") == "clarification":
        return {"answer_type": answer_type, "answer": answer, "referral_reasons": []}
    if draft.get("kind") != "clarification" and answer_type != "clarification_needed":
        answer = draft.get("text") or answer
    reasons = referral.decide(intent=it, critic=state.get("critic"), verdicts=state.get("verdicts") or [],
                              focus_ids=(state.get("focus") or []) if state.get("mode") != "discovery" else [],
                              tool_failures=state.get("tool_failures") or [],
                              overdue_apps=state.get("overdue") or [], conv_turns=state["conv"].get("turns", 0),
                              repeat_threshold=int(tools.policy(state["conn"], "repeated_contact_threshold", state["as_of"])),
                              critic_threshold=float(tools.policy(state["conn"], "critic_min_groundedness", state["as_of"])))
    if state.get("overdue"):
        reasons = list(dict.fromkeys(reasons + ["delay_beyond_timeline"]))
    if answer_type == "confirmation_needed":
        reasons = [r for r in reasons if r in {"explicit_human_request"}]
    return {"answer_type": answer_type, "answer": answer if draft.get("kind") != "not_found" else t("not_found", state["lang"]),
            "referral_reasons": reasons}


def after_policy(state: S) -> str:
    return "referral" if state.get("referral_reasons") else "finalize"


@_timed("referral")
def referral_node(state: S) -> dict:
    conn, it, lang, as_of = state["conn"], state["intent"], state["lang"], state["as_of"]
    calls = list(state.get("tool_calls") or [])
    reasons = list(state.get("referral_reasons") or [])
    apps = state.get("apps") or []
    overdue = list(state.get("overdue") or [])
    target = int(tools.policy(conn, "application_processing_target_days", as_of))
    citizen = state["citizen"]
    if it.type in {"grievance", "fraud_report"} and citizen.get("attributes") is not None and not apps:
        apps = tools.get_applications(conn, state["citizen_id"])
        calls.append(ToolCall(tool="get_applications", input={"citizen_id": state["citizen_id"]}, output=apps))
        overdue = [a for a in apps if a["status"] == "submitted" and a["status_updated_on"] and
                   (date.fromisoformat(as_of) - date.fromisoformat(a["status_updated_on"])).days > target]
    if not reasons:
        reasons = referral.decide(intent=it, critic=state.get("critic"), verdicts=state.get("verdicts") or [],
                                  focus_ids=state.get("focus") or [], tool_failures=state.get("tool_failures") or [],
                                  overdue_apps=overdue, conv_turns=state["conv"].get("turns", 0),
                                  repeat_threshold=int(tools.policy(conn, "repeated_contact_threshold", as_of)),
                                  critic_threshold=float(tools.policy(conn, "critic_min_groundedness", as_of)))
    queue, priority = referral.queue_and_priority(reasons, it)
    sla = int(tools.policy(conn, referral.sla_parameter(priority), as_of))
    evidence: list[dict[str, Any]] = []
    if apps:
        evidence.append({"tool": "get_applications", "output": apps})
    if {"bribe_demand", "fraud_attempt"} & set(reasons):
        evidence.append({"source_id": "POL-FEE-01", "section": "2 No fee for applications"})
    if "fraud_attempt" in reasons:
        evidence.append({"source_id": "CIR-2026-008", "section": "fraud advisory"})
    evidence += referral.verdict_evidence([v for v in state.get("verdicts") or [] if v.verdict == "verify_with_officer"
                                           and v.scheme_id in (state.get("focus") or [])])
    if state.get("critic") is not None:
        evidence.append({"critic": state["critic"].model_dump()})
    attempted = (state.get("draft") or {}).get("text") or ""
    if it.type in {"grievance", "fraud_report"}:
        attempted = ("Stated the no-fee rule and the referral route; no outcome promised." if
                     {"bribe_demand", "fraud_attempt"} & set(reasons) else
                     "Acknowledged the issue and explained the referral route; no outcome promised.")
    unresolved = referral.unresolved_questions(reasons, overdue, [v for v in state.get("verdicts") or []
                                                                  if v.scheme_id in (state.get("focus") or [])], apps, target)
    bundle = referral.build_bundle(reasons=reasons, queue=queue, priority=priority, intent=it,
                                   message_redacted=state["message_redacted"], evidence=evidence,
                                   attempted_answer=attempted[:600], unresolved=unresolved,
                                   conversation_id=state["conversation_id"], citizen_id=state["citizen_id"],
                                   language=lang, as_of=as_of, sla_days=sla, trace_id=state["trace_id"],
                                   attributes=state.get("attrs") or {})
    rid = tools.create_referral(conn, conversation_id=state["conversation_id"], citizen_id=state["citizen_id"],
                                queue=queue, priority=priority, bundle=bundle, as_of=as_of)
    calls.append(ToolCall(tool="create_referral", input={"queue": queue, "priority": priority},
                          output={"referral_id": rid, "reasons": reasons}))
    prior = (state.get("draft") or {})
    if reasons == ["verify_with_officer"] and prior.get("text"):
        answer = prior["text"] + "\n" + t("provisional_referred", lang, rid=rid)
    elif prior.get("kind") in {"app_status"} and prior.get("text"):
        answer = prior["text"] + "\n" + referral.citizen_message(reasons=reasons, queue=queue, sla=sla, lang=lang, rid=rid)
    else:
        answer = referral.citizen_message(reasons=reasons, queue=queue, sla=sla, lang=lang, rid=rid)
    cites = list((state.get("draft") or {}).get("cites") or [])
    if {"bribe_demand", "fraud_attempt"} & set(reasons):
        cites.append(("POL-FEE-01", "2"))
    if "fraud_attempt" in reasons:
        cites.append(("CIR-2026-008", ""))
    cites.append(("POL-GRV-01", "3"))
    draft = dict(state.get("draft") or {"kind": "referral", "used_hits": []})
    draft["cites"] = list(dict.fromkeys(cites))
    return {"answer_type": "referred", "answer": answer, "referral_id": rid, "referral": bundle, "tool_calls": calls,
            "referral_reasons": reasons, "draft": draft, "apps": apps, "overdue": overdue,
            "pending_action": None}


def _citations(state: S) -> list[Citation]:
    conn, lang = state["conn"], state["lang"]
    draft = state.get("draft") or {}
    cites = draft.get("cites") or []
    hits = state.get("retrieved")
    if hits is None:
        hits = []
        state["retrieved"] = hits  # finalize writes the audit record from this same dict
    out: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for sid, sec in cites:
        if not sid:
            continue
        src = db.row(conn, "SELECT * FROM sources WHERE source_id=?", (sid,))
        if not src or int(src.get("authority_level") or 5) >= 5:
            continue
        section = sec
        cand = [h for h in hits if h["source_id"] == sid]
        if not cand or (sec and not any(h["section"].split(" ")[0] == sec.split(" ")[0] for h in cand)):
            # a citation added after retrieval (e.g. the no-fee rule in a referral): fetch the exact
            # section so every cited passage is in the audited retrieval output
            try:
                p = vs.get_section(sid, sec or "2") or vs.get_section(sid, "1")
            except Exception:
                p = None
            if p:
                hits.append(p)
                cand.append(p)
        if sec:
            match = [h for h in cand if h["section"].split(" ")[0] == sec.split(" ")[0]]
            if match:
                section = match[0]["section"]
        elif cand:
            non_header = [h for h in cand if h["section"] != "0 Header"] or cand
            non_header.sort(key=lambda h: not h.get("pinned"))
            section = non_header[0]["section"]
        key = (sid, section.split(" ")[0])
        if key in seen:
            continue
        seen.add(key)
        out.append(Citation(source_id=sid, doc_type=src["doc_type"], title=src.get("title") or "", section=section,
                            scheme_id=src.get("scheme_id") or None, language=src.get("language") or "en",
                            effective_from=src.get("effective_from") or None, last_updated=src.get("last_updated") or None,
                            label=i18n.citation_label(sid, section, lang)))
    return out


@_timed("finalize")
def finalize(state: S) -> dict:
    conn, lang = state["conn"], state["lang"]
    answer_type = state.get("answer_type") or "answered"
    answer = state.get("answer") or ""
    critic_out = state.get("critic")
    if critic_out is not None and critic_out.pii_risk != "none":
        answer = pii.redact(answer)[0]
    answer = pii.redact(answer)[0]  # never echo a secret, whatever happened upstream
    if state.get("pii_types") and answer_type not in {"refused"}:
        answer = t("pii_warning", lang) + "\n" + answer
    citations = _citations(state) if answer_type in {"answered", "referred", "confirmation_needed"} else []
    if citations and answer_type in {"answered", "referred"}:
        labels = "; ".join(c.label for c in citations[:3])
        answer = f"{answer}\n({labels})"
    conv = dict(state["conv"])
    conv.update(state.get("state_updates") or {})
    conv["turns"] = conv.get("turns", 0) + 1
    conv["reply_language"] = lang
    if state.get("referral_id"):
        conv["referrals"] = (conv.get("referrals") or []) + [state["referral_id"]]
    memory.save_state(conn, state["conversation_id"], conv)
    memory.add_message(conn, state["conversation_id"], "user", state["message"])
    route = list(state.get("route") or []) + ["finalize"]
    memory.add_message(conn, state["conversation_id"], "assistant", answer, state["trace_id"], answer_type, route)
    total_ms = round((time.perf_counter() - state["t0"]) * 1000, 1)
    it: IntentOut = state["intent"]
    record = {
        "trace_id": state["trace_id"], "conversation_id": state["conversation_id"], "citizen_id": state["citizen_id"],
        "as_of_date": state["as_of"], "channel": state["req"].channel,
        "consent_profile_used": bool((state.get("citizen") or {}).get("attributes")),
        "message_redacted": state["message_redacted"], "pii_detected": state.get("pii_types") or [],
        "intent": it.model_dump(), "classifier": state.get("cls_debug"), "reply_language": lang, "route": route,
        "answer_type": answer_type,
        "attributes_used": {k: {"value": v, "source": (state.get("attr_sources") or {}).get(k)}
                            for k, v in (state.get("attrs") or {}).items()},
        "sources_retrieved": [{"source_id": h["source_id"], "section": h["section"], "score": h["score"],
                               "language": h["meta"].get("language"), "authority_level": h["meta"].get("authority_level"),
                               "pinned": bool(h.get("pinned"))} for h in state.get("retrieved") or []],
        "citations": [c.model_dump() for c in citations],
        "tools_invoked": [c.model_dump() for c in state.get("tool_calls") or []],
        "rules_evaluated": [v.model_dump()
                            for v in state.get("verdicts") or [] if v.scheme_id in (state.get("focus") or [])],
        "questions_asked": [q.model_dump() for q in state.get("questions") or []],
        "actions_proposed": [state["pending_action"].model_dump()] if state.get("pending_action") else [],
        "actions_confirmed": [],
        "critic": critic_out.model_dump() if critic_out is not None else None,
        "referral": {"referral_id": state.get("referral_id"), "reasons": state.get("referral_reasons") or []},
        "referral_summary": state.get("referral"),
        "conflicts_detected": state.get("conflicts") or [],
        "model": {"mode": llm.mode, "name": None if llm.mock else llm.model, "embedding": vs.get_embedder().model_name},
        "llm": state["stats"].as_dict(), "latency_ms": {"total": total_ms, **(state.get("timings") or {})},
    }
    memory.save_audit(conn, state["trace_id"], state["conversation_id"], record)
    return {"answer": answer, "answer_type": answer_type, "citations_final": citations, "route": route}


# ------------------------------------------------------------------ graph assembly
def build_graph():
    g = StateGraph(S)
    g.add_node("guard", guard)
    g.add_node("classify", classify)
    g.add_node("respond", respond)
    g.add_node("eligibility", eligibility)
    g.add_node("knowledge", knowledge)
    g.add_node("retrieve", retrieve)
    g.add_node("action", action)
    g.add_node("critique", critic_node)
    g.add_node("revise", revise)
    g.add_node("policy", policy_node)
    g.add_node("refer", referral_node)
    g.add_node("finalize", finalize)
    g.set_entry_point("guard")
    g.add_edge("guard", "classify")
    g.add_conditional_edges("classify", route, {"respond": "respond", "eligibility": "eligibility",
                                                "knowledge": "knowledge", "action": "action", "referral": "refer"})
    g.add_edge("respond", "finalize")
    g.add_conditional_edges("eligibility", lambda s: "finalize" if s.get("answer_type") == "clarification_needed" else "retrieve",
                            {"finalize": "finalize", "retrieve": "retrieve"})
    g.add_conditional_edges("knowledge", lambda s: "finalize" if s.get("answer_type") == "clarification_needed" else "retrieve",
                            {"finalize": "finalize", "retrieve": "retrieve"})
    g.add_edge("retrieve", "critique")
    g.add_edge("action", "critique")
    g.add_conditional_edges("critique", after_critic, {"revise": "revise", "policy": "policy"})
    g.add_edge("revise", "critique")
    g.add_conditional_edges("policy", after_policy, {"referral": "refer", "finalize": "finalize"})
    g.add_edge("refer", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


GRAPH = build_graph()


def run_ask(req: AskRequest, citizen_id: str) -> AskResponse:
    as_of = req.as_of_date or tools.now_ist().date().isoformat()
    trace_id = memory.new_trace_id()
    with db.get_conn() as conn:
        state: S = {"conn": conn, "req": req, "citizen_id": citizen_id or "guest", "as_of": as_of, "trace_id": trace_id,
                    "t0": time.perf_counter(), "stats": LLMStats(), "timings": {}, "route": [], "revisions": 0}
        out = GRAPH.invoke(state, {"recursion_limit": 30})
        it: IntentOut = out["intent"]
        critic_out = out.get("critic")
        return AskResponse(
            trace_id=trace_id, conversation_id=out["conversation_id"], answer_type=out["answer_type"],
            language=out["lang"], answer=out["answer"], intent=it, citations=out.get("citations_final") or [],
            tools_invoked=[ToolCall(**{**c.model_dump(), "output": pii.redact_obj(c.output)}) for c in out.get("tool_calls") or []],
            eligibility=[v for v in out.get("verdicts") or [] if v.scheme_id in (out.get("focus") or [])],
            questions=out.get("questions") or [], pending_action=out.get("pending_action"), critic=critic_out,
            conflicts_detected=out.get("conflicts") or [], referral_id=out.get("referral_id"),
            referral=out.get("referral"), as_of_date=as_of)
