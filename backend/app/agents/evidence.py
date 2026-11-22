"""Evidence the critic checks a draft against (R7), split the way Annex A.2 needs it:

* general   - evidence not tied to one scheme (policy registry, action payloads, non-scheme sources)
* scoped    - per scheme: its rule rows in force, its effective dates, its scheme row, its sources
* historical- FAQs and resolved grievances (authority 4): never enough on their own
* superseded/current - per scheme, values an amendment replaced vs values in force today
* citizen   - values the citizen gave (attributes), which may always be repeated back"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from typing import Any

from .. import db, tools
from ..rules import engine
from .critic import _numbers


def _j(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def build(conn: sqlite3.Connection, as_of: str, *, retrieved: list[dict[str, Any]] | None = None,
          tool_calls: list[Any] | None = None, extra: list[str] | None = None, attrs: dict[str, Any] | None = None,
          cites: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    schemes = tools.list_schemes(conn)
    general: list[str] = [_j(db.rows(conn, "SELECT parameter, value FROM policy_registry"))]
    general += list(extra or [])
    general += [f"{sid} {sec}" for sid, sec in (cites or [])]
    scoped: dict[str, list[str]] = defaultdict(list)
    superseded: dict[str, set[str]] = defaultdict(set)
    current: dict[str, set[str]] = defaultdict(set)
    for s in schemes:
        sid = s["scheme_id"]
        st = tools.scheme_status(conn, s, as_of)
        in_force = engine.rules_in_force(conn, sid, as_of)
        scoped[sid] += [_j(s), _j(st), _j(in_force)]
        future = [r for r in engine.all_rules(conn, sid) if r["effective_from"] and r["effective_from"] > as_of]
        scoped[sid].append(_j(future))  # announced changes may be stated with their date
        for r in in_force + future:
            current[sid] |= _numbers(str(r["value"]))
        for d in (st.get("apply_until"), st.get("apply_from")):
            if d:
                current[sid] |= _numbers(d)
        current[sid] |= _numbers(s.get("benefit_summary") or "")
        for r in engine.all_rules(conn, sid):
            if r["valid_until"] and r["valid_until"] < as_of:
                superseded[sid] |= _numbers(str(r["value"])) - current[sid]
        for n in st.get("notes", []):
            if n["type"] == "deadline_extended":
                superseded[sid] |= _numbers(n["old"]) - current[sid]
    historical: list[str] = []
    for h in retrieved or []:
        lvl = int(h["meta"].get("authority_level") or 5)
        text = f"{h['text']} {h['section']}"
        if lvl >= 4:
            historical.append(text)
        elif h["meta"].get("scheme_id"):
            scoped[h["meta"]["scheme_id"]].append(text)
        else:
            general.append(text)
    for c in tool_calls or []:
        sid = (c.input or {}).get("scheme_id") if hasattr(c, "input") else None
        out = _j(c.output if hasattr(c, "output") else c)
        tool = getattr(c, "tool", "")
        if isinstance(sid, str) and sid:
            scoped[sid].append(out)
        elif tool in {"check_eligibility", "get_scheme", "search_knowledge_base"}:
            continue  # covered per scheme above; adding them whole would let one scheme "support" another
        else:
            general.append(out)
    citizen = [_j(attrs or {})]
    return {"general": general, "scoped": dict(scoped), "historical": historical, "superseded": dict(superseded),
            "current": dict(current), "citizen": citizen, "schemes": schemes}
