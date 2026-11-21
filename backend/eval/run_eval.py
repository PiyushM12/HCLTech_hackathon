"""SchemeSathi evaluation (Section 7 of the guide).

    python eval/run_eval.py            # MOCK_LLM pipeline, real multilingual embeddings
    MOCK_LLM=false python eval/run_eval.py   # same, with Ollama for classification / free text

Runs in an isolated runtime folder (eval/.runtime) so it never touches the app's database.
Writes eval/results.json, eval/report.md and docs/samples/*.json."""
from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
RUNTIME = HERE / ".runtime"
if "--reuse" not in sys.argv:
    shutil.rmtree(RUNTIME, ignore_errors=True)
RUNTIME.mkdir(exist_ok=True)
os.environ["RUNTIME_DIR"] = str(RUNTIME)
os.environ["DB_PATH"] = str(RUNTIME / "eval.db")
os.environ["CHROMA_DIR"] = str(RUNTIME / "chroma")
os.environ.setdefault("MOCK_LLM", "true")
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, config, db, tools  # noqa: E402
from app.agents import critic as critic_mod  # noqa: E402
from app.kb import ingest as kb_ingest  # noqa: E402
from app.kb import vectorstore as vs  # noqa: E402
from app.llm import llm  # noqa: E402
from app.main import app  # noqa: E402
from app.nlp import lang as langmod  # noqa: E402
from app.nlp import pii  # noqa: E402

AS_OF = "2026-11-21"
SAMPLES = BACKEND.parent / "docs" / "samples"


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}% ({n}/{d})" if d else "n/a"


# ------------------------------------------------------------------ end-to-end cases
def evaluation_client(stack: ExitStack, citizen_id: str | None = None) -> TestClient:
    username = citizen_id.lower() if citizen_id else "eval-admin"
    role = "user" if citizen_id else "admin"
    # These accounts exist only in the isolated evaluation database.
    password = "isolated-evaluation-password"
    with db.get_conn() as conn:
        exists = db.row(conn, "SELECT 1 FROM auth_accounts WHERE username=?", (username,))
    if not exists:
        auth.create_account(username, password, role, citizen_id)
    client = TestClient(app)
    stack.callback(client.close)
    client.post("/auth/login", json={"username": username, "password": password, "role": role}).raise_for_status()
    return client


def run_cases(guest: TestClient, stack: ExitStack) -> tuple[list[dict], list[float]]:
    results, latencies = [], []
    clients = {"guest": guest}
    for case in load_jsonl("eval_set.jsonl"):
        exp = case["expect"]
        conv = None
        responses = []
        turn_type_ok = True
        for turn in case["turns"]:
            citizen_id = turn.get("citizen_id", "guest")
            if citizen_id not in clients:
                clients[citizen_id] = evaluation_client(stack, citizen_id)
            c = clients[citizen_id]
            body = {"message": turn["message"], "as_of_date": AS_OF}
            if conv:
                body["conversation_id"] = conv
            t0 = time.perf_counter()
            r = c.post("/ask", json=body)
            r.raise_for_status()
            latencies.append((time.perf_counter() - t0) * 1000)
            d = r.json()
            conv = d["conversation_id"]
            responses.append(d)
            if turn.get("expect_type") and d["answer_type"] != turn["expect_type"]:
                turn_type_ok = False
        final = responses[-1]
        checks: dict[str, bool] = {"turn_types": turn_type_ok}
        action_result = None
        if exp.get("action") and final.get("pending_action"):
            aid = final["pending_action"]["action_id"]
            if exp["action"] == "confirm":
                action_result = c.post(f"/actions/{aid}/confirm").json()
                checks["action"] = action_result.get("verified") is True and action_result["answer_type"] == "action_completed"
            else:
                action_result = c.post(f"/actions/{aid}/cancel").json()
                checks["action"] = action_result["action"]["status"] == "cancelled"
            checks["action_type"] = final["pending_action"]["action_type"] == exp.get("action_type")
        elif exp.get("action"):
            checks["action"] = False
        if "answer_type" in exp:
            checks["answer_type"] = final["answer_type"] == exp["answer_type"]
        if "language" in exp:
            checks["language"] = final["language"] == exp["language"]
        for s in exp.get("contains", []):
            checks[f"contains:{s}"] = s in final["answer"]
        for s in exp.get("not_contains", []):
            checks[f"not_contains:{s}"] = s not in final["answer"]
        got_verdicts = {v["scheme_id"]: v for v in final.get("eligibility") or []}
        for sid, ver in exp.get("verdicts", {}).items():
            checks[f"verdict:{sid}"] = got_verdicts.get(sid, {}).get("verdict") == ver
        got_rules = {r["rule_id"]: r["result"] for v in got_verdicts.values() for r in v["rules"]}
        for rid, res in exp.get("rules", {}).items():
            checks[f"rule:{rid}"] = got_rules.get(rid) == res
        cited = {x["source_id"] for x in final["citations"]}
        if exp.get("cites_any"):
            checks["cites_expected"] = bool(cited & set(exp["cites_any"]))
        for s in exp.get("not_cited", []):
            checks[f"not_cited:{s}"] = s not in cited
        blob = json.dumps(responses, ensure_ascii=False)
        for s in exp.get("no_leak", []):
            checks[f"no_leak:{s}"] = s not in blob
        referred = final["answer_type"] == "referred" or bool(final.get("referral_id"))
        if "referred" in exp:
            checks["referral_decision"] = referred == exp["referred"]
        if exp.get("queue"):
            checks["queue"] = (final.get("referral") or {}).get("queue") == exp["queue"]
        for reason in exp.get("reasons", []):
            checks[f"reason:{reason}"] = reason in (final.get("referral") or {}).get("referral_reasons", [])
        if exp.get("no_verdict"):
            checks["no_verdict"] = not final.get("eligibility")
        asked = [q["attribute"] for d in responses for q in d.get("questions") or []]
        if "max_questions" in exp:
            checks["max_questions"] = len(asked) <= exp["max_questions"]
        checks["max_two_per_turn"] = all(len(d.get("questions") or []) <= 2 for d in responses)
        results.append({"id": case["id"], "category": case["category"], "group": case.get("group"),
                        "passed": all(checks.values()), "checks": checks, "responses": responses,
                        "action_result": action_result, "expected_referred": exp.get("referred"),
                        "referred": referred, "questions": asked,
                        "repeated_questions": len(asked) - len(set(asked))})
    return results, latencies


# ------------------------------------------------------------------ retrieval
def _equivalent(found: str, expected: list[str]) -> bool:
    """A translated summary of the expected document (GL-PEN-01-KN for GL-PEN-01) has the same content."""
    return any(found == e or found.startswith(e + "-") or e.startswith(found + "-") for e in expected)


def retrieval_eval(model_name: str, collection, embedder, scheme_boost: bool = False) -> dict:
    from app.nlp import extract
    rows = load_jsonl("retrieval_set.jsonl")
    with db.get_conn() as conn:
        all_schemes = tools.list_schemes(conn)
    with db.get_conn() as conn:
        langs = {r["source_id"]: r["language"] for r in db.rows(conn, "SELECT source_id, language FROM sources")}
    per_pair: dict[str, list[int]] = defaultdict(list)
    per_pair_eq: dict[str, list[int]] = defaultdict(list)
    rr: list[float] = []
    details = []
    for r in rows:
        sids = extract.mentioned_schemes(r["q"], all_schemes) if scheme_boost else None
        hits = vs.search(r["q"], k=6, as_of=AS_OF, collection=collection, embedder=embedder, scheme_ids=sids or None)
        ids = [h["source_id"] for h in hits]
        rank = next((i + 1 for i, s in enumerate(ids) if s in r["expected"]), None)
        eq = any(_equivalent(s, r["expected"]) for s in ids)
        pair = f"{r['lang']}→{langs.get(r['expected'][0], '?')}"
        per_pair[pair].append(1 if rank else 0)
        per_pair_eq[pair].append(1 if eq else 0)
        rr.append(1 / rank if rank else 0.0)
        details.append({"q": r["q"], "pair": pair, "rank": rank, "equivalent_hit": eq, "top": ids[:3]})
    total = sum(sum(v) for v in per_pair.values())
    total_eq = sum(sum(v) for v in per_pair_eq.values())
    name = model_name.split("/")[-1] + (" + scheme boost" if scheme_boost else "")
    return {"model": name, "hit_at_6": total / len(rows), "equivalent_hit_at_6": total_eq / len(rows),
            "mrr": sum(rr) / len(rr), "n": len(rows),
            "per_pair": {k: {"hits": sum(v), "n": len(v), "rate": sum(v) / len(v),
                             "equivalent": sum(per_pair_eq[k])} for k, v in sorted(per_pair.items())},
            "details": details}


def build_alt_collection(model_name: str):
    """Index the same chunks with a second embedding model, for the comparison."""
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(RUNTIME / f"chroma_{model_name.split('/')[-1]}"),
                                       settings=Settings(anonymized_telemetry=False))
    col = client.get_or_create_collection("alt", metadata={"hnsw:space": "cosine"})
    emb = vs.Embedder("sentence-transformers", model_name)
    if col.count() == 0:
        main = vs.get_collection()
        data = main.get(include=["documents", "metadatas"])
        by_src: dict[str, list] = defaultdict(list)
        for doc, meta in zip(data["documents"], data["metadatas"]):
            by_src[meta["source_id"]].append({"text": doc, "meta": meta})
        for sid, chunks in by_src.items():
            vs.upsert_chunks(sid, chunks, collection=col, embedder=emb)
    return col, emb


# ------------------------------------------------------------------ critic agreement
def critic_eval() -> dict:
    from app.agents import evidence as evidence_mod
    rows = load_jsonl("critic_set.jsonl")
    evs = {}
    with db.get_conn() as conn:
        for r in rows:
            evs[r["id"]] = evidence_mod.build(conn, AS_OF, attrs=r.get("citizen"),
                                              cites=[("GL-PEN-01", "3"), ("CIR-2026-011", "2")])
    configs = {"critic (threshold 0.8)": 0.8, "critic (threshold 0.5)": 0.5,
               "critic without scheme scoping (0.8)": "unscoped", "no critic (always answer)": None}
    out = {}
    for name, th in configs.items():
        agree, conf = 0, Counter()
        per = []
        for r in rows:
            ev = evs[r["id"]]
            if th is None:
                decision = "answer"
            elif th == "unscoped":  # the first version: all evidence in one pool, no superseded check
                pool = ev["general"] + [x for v in ev["scoped"].values() for x in v] + ev["citizen"]
                o = critic_mod.review(draft={"text": r["text"], "cites": [("GL-PEN-01", "3")], "kind": "eligibility",
                                             "used_hits": []}, lang=r["lang"], evidence_authoritative=pool,
                                      evidence_historical=r.get("historical", []), retrieved=[], answer_kind="eligibility",
                                      has_verdict=r["verdict"], threshold=0.8, revisions=0, max_revisions=1)
                decision = o.decision
            else:
                o = critic_mod.review(draft={"text": r["text"], "cites": [("GL-PEN-01", "3")], "kind": "eligibility",
                                             "used_hits": []}, lang=r["lang"], evidence_authoritative=ev["general"],
                                      evidence_historical=r.get("historical", []), retrieved=[], answer_kind="eligibility",
                                      has_verdict=r["verdict"], threshold=th, revisions=0, max_revisions=1,
                                      evidence_scoped=ev["scoped"], superseded=ev["superseded"], current=ev["current"],
                                      citizen_values=ev["citizen"], schemes=ev["schemes"])
                decision = o.decision
            critic_bad = decision != "answer"
            human_bad = r["human"] == "bad"
            agree += critic_bad == human_bad
            conf[("flagged" if critic_bad else "passed", r["human"])] += 1
            per.append({"id": r["id"], "note": r["note"], "human": r["human"], "critic": decision})
        out[name] = {"agreement": agree / len(rows), "n": len(rows), "confusion": {f"{a}/{b}": v for (a, b), v in conf.items()},
                     "per_item": per}
    return out


# ------------------------------------------------------------------ PII scan
SEEDED_SECRETS = ["482913", "123456789012345", "1234 5678 9012", "9876543210"]


def pii_scan(results: list[dict]) -> dict:
    leaks = []
    with db.get_conn() as conn:
        audits = [r["record_json"] for r in db.rows(conn, "SELECT record_json FROM audit")]
        bundles = [r["bundle_json"] for r in db.rows(conn, "SELECT bundle_json FROM referrals")]
        msgs = [r["text"] for r in db.rows(conn, "SELECT text FROM messages")]
    for kind, items in [("response", [json.dumps(x["responses"], ensure_ascii=False) for x in results]),
                        ("audit", audits), ("referral_bundle", bundles), ("message_log", msgs)]:
        for i, text in enumerate(items):
            for s in SEEDED_SECRETS:
                if s in text:
                    leaks.append({"where": kind, "index": i, "secret": s})
            for x in results if kind == "response" else []:
                for d in x["responses"]:
                    found = pii.detect(d["answer"])
                    if found:
                        leaks.append({"where": "answer", "case": x["id"], "types": found})
                break
    return {"leaks": leaks, "audit_records": len(audits), "bundles": len(bundles), "messages": len(msgs)}


def language_fidelity(results: list[dict]) -> dict:
    per_lang: dict[str, list[int]] = defaultdict(list)
    for x in results:
        for d in x["responses"]:
            if d["answer_type"] in {"answered", "referred", "clarification_needed", "confirmation_needed"}:
                text = d["answer"].split("\n(")[0]
                share = langmod.script_share(critic_mod.ID_TOKEN.sub(" ", text).replace("(", " "), d["language"])
                ok = share >= (0.5 if d["language"] in {"hi", "kn", "ta"} else 0.7)
                per_lang[d["language"]].append(1 if ok else 0)
    groups: dict[str, list] = defaultdict(list)
    for x in results:
        if x["group"]:
            final = x["responses"][-1]
            groups[x["group"]].append({"id": x["id"], "numbers": sorted(critic_mod._numbers(final["answer"].split("\n(")[0])),
                                       "verdicts": {v["scheme_id"]: v["verdict"] for v in final.get("eligibility") or []}})
    consistency = {g: {"same_numbers": len({tuple(m["numbers"]) for m in ms}) == 1,
                       "same_verdicts": len({json.dumps(m["verdicts"], sort_keys=True) for m in ms}) == 1,
                       "members": ms} for g, ms in groups.items()}
    return {"script_match": {k: {"ok": sum(v), "n": len(v)} for k, v in per_lang.items()}, "cross_language": consistency}


def citation_validity(c: TestClient, results: list[dict]) -> dict:
    known = {s["source_id"] for s in c.get("/sources").json()}
    total = valid = in_retrieval = 0
    bad = []
    for x in results:
        for d in x["responses"]:
            if not d["citations"]:
                continue
            rec = c.get(f"/audit/{d['trace_id']}").json()
            retrieved = {(s["source_id"]) for s in rec.get("sources_retrieved", [])}
            for cit in d["citations"]:
                total += 1
                ok_exist = cit["source_id"] in known
                ok_ret = cit["source_id"] in retrieved
                valid += ok_exist
                in_retrieval += ok_ret
                if not (ok_exist and ok_ret):
                    bad.append({"case": x["id"], "source_id": cit["source_id"], "exists": ok_exist, "retrieved": ok_ret})
    with_expect = [x for x in results if "cites_expected" in x["checks"]]
    return {"citations": total, "exist": valid, "in_retrieval_output": in_retrieval, "problems": bad,
            "expected_source_cited": sum(x["checks"]["cites_expected"] for x in with_expect), "cases_with_expectation": len(with_expect)}


def export_samples(c: TestClient, results: list[dict]) -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    pick = {"audit_eligibility_hi.json": "HI-01", "audit_referral_bribe.json": "RF-01", "audit_critic_revision.json": "PI-01"}
    for fname, cid in pick.items():
        x = next(r for r in results if r["id"] == cid)
        rec = c.get(f"/audit/{x['responses'][-1]['trace_id']}").json()
        (SAMPLES / fname).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    for fname, cid in {"referral_bundle_grievance.json": "RF-01", "referral_bundle_fraud.json": "RF-02"}.items():
        x = next(r for r in results if r["id"] == cid)
        b = c.get(f"/referrals/{x['responses'][-1]['referral_id']}").json()
        (SAMPLES / fname).write_text(json.dumps({"response": x["responses"][-1], "referral": b}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    x = next(r for r in results if r["id"] == "AC-01")
    flow = {"1_propose": x["responses"][-1], "2_confirm_execute_verify": x["action_result"]}
    with db.get_conn() as conn:
        res = x["action_result"]["result"]
        flow["3_database_after"] = {
            "appointment": db.row(conn, "SELECT * FROM appointments WHERE appointment_id=?", (res["appointment_id"],)),
            "reminder": db.row(conn, "SELECT * FROM reminders WHERE reminder_id=?", (res.get("reminder_id"),)),
            "action": db.row(conn, "SELECT action_id, action_type, status, created_at, expires_at, executed_at FROM actions "
                                   "WHERE action_id=?", (x["responses"][-1]["pending_action"]["action_id"],))}
    (SAMPLES / "action_flow_booking.json").write_text(json.dumps(flow, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ------------------------------------------------------------------ report
def main() -> None:
    t_start = time.time()
    with TestClient(app) as guest, ExitStack() as stack:
        admin = evaluation_client(stack)
        results, latencies = run_cases(guest, stack)
        cit = citation_validity(admin, results)
        export_samples(admin, results)
        audits = [admin.get(f"/audit/{d['trace_id']}").json() for x in results for d in x["responses"]]
    configs = [retrieval_eval(config.EMBEDDING_MODEL, None, None),
               retrieval_eval(config.EMBEDDING_MODEL, None, None, scheme_boost=True)]
    for alt_name in ["sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "BAAI/bge-m3"]:
        if alt_name == config.EMBEDDING_MODEL:
            continue
        try:
            col, emb = build_alt_collection(alt_name)
            configs.append(retrieval_eval(alt_name, col, emb))
            configs.append(retrieval_eval(alt_name, col, emb, scheme_boost=True))
        except Exception as e:  # model not downloaded: report it instead of guessing
            configs.append({"model": alt_name.split("/")[-1], "error": str(e)[:200]})
    crit = critic_eval()
    lf = language_fidelity(results)
    leak = pii_scan(results)

    by_cat: dict[str, list] = defaultdict(list)
    for x in results:
        by_cat[x["category"]].append(x["passed"])
    verdict_checks = [(k, v) for x in results for k, v in x["checks"].items() if k.startswith("verdict:")]
    rule_checks = [(k, v) for x in results for k, v in x["checks"].items() if k.startswith("rule:")]
    tp = sum(1 for x in results if x["expected_referred"] and x["referred"])
    fp = sum(1 for x in results if x["expected_referred"] is False and x["referred"])
    fn = sum(1 for x in results if x["expected_referred"] and not x["referred"])
    tn = sum(1 for x in results if x["expected_referred"] is False and not x["referred"])
    multi = [x for x in results if x["category"] == "multi_turn"]
    resolved = [x for x in results if x["questions"] and x["passed"]]
    llm_calls = [a.get("llm", {}).get("calls", 0) for a in audits]
    tokens = [a.get("llm", {}).get("prompt_tokens", 0) + a.get("llm", {}).get("completion_tokens", 0) for a in audits]
    revisions = sum(1 for a in audits if (a.get("critic") or {}).get("revisions"))
    q = statistics.quantiles(latencies, n=20) if len(latencies) > 2 else [0] * 19
    summary = {
        "mode": {"llm": llm.mode, "model": None if llm.mock else llm.model, "embedding": config.EMBEDDING_MODEL, "as_of": AS_OF},
        "cases": len(results), "passed": sum(x["passed"] for x in results),
        "by_category": {k: {"passed": sum(v), "n": len(v)} for k, v in sorted(by_cat.items())},
        "eligibility": {"scheme_verdicts": {"ok": sum(v for _, v in verdict_checks), "n": len(verdict_checks)},
                        "rules": {"ok": sum(v for _, v in rule_checks), "n": len(rule_checks)}},
        "citations": cit, "retrieval": {"configs": configs}, "critic": crit, "language": lf,
        "referral_confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                               "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None},
        "questions": {"multi_turn_cases": len(multi),
                      "avg_questions_per_resolved_case": (sum(len(x["questions"]) for x in resolved) / len(resolved)) if resolved else 0,
                      "repeated_questions": sum(x["repeated_questions"] for x in results),
                      "turns_over_two_questions": sum(1 for x in results if not x["checks"]["max_two_per_turn"])},
        "pii": leak, "critic_revisions_in_run": revisions,
        "latency_ms": {"p50": statistics.median(latencies), "p95": q[18], "max": max(latencies), "n": len(latencies)},
        "llm": {"calls_per_request": statistics.mean(llm_calls) if llm_calls else 0,
                "tokens_per_request": statistics.mean(tokens) if tokens else 0},
        "failures": [{"id": x["id"], "failed_checks": [k for k, v in x["checks"].items() if not v]}
                     for x in results if not x["passed"]],
        "runtime_s": round(time.time() - t_start, 1),
    }
    (HERE / "results.json").write_text(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    write_report(summary)
    print(json.dumps({k: summary[k] for k in ("cases", "passed", "referral_confusion", "latency_ms")}, indent=1, default=str))
    print("failures:", summary["failures"])


def write_report(s: dict) -> None:
    L = []
    add = L.append
    add("# SchemeSathi evaluation report\n")
    add(f"Generated by `eval/run_eval.py`. LLM mode: **{s['mode']['llm']}**"
        + (f" ({s['mode']['model']})" if s['mode']['model'] else "") + f"; embeddings: `{s['mode']['embedding']}`; "
        f"as-of date {s['mode']['as_of']}. Runtime {s['runtime_s']} s.\n")
    add("## Method\n")
    add("- **End-to-end set** (`eval/eval_set.jsonl`): labelled requests run through the real API in an isolated "
        "database. Each case lists the checks it must pass: answer type, reply language, required/forbidden text, "
        "per-scheme verdict, per-rule result, expected citation, referral decision/queue/reasons, action outcome, "
        "no-leak strings and question limits. A case passes only if every check passes.")
    add("- **Retrieval set** (`eval/retrieval_set.jsonl`): questions in en/hi/kn/ta whose answer sits in a document "
        "of a stated language. Hit@6 = the expected document is in the top 6. Reported per language pair "
        "(question language → document language).")
    add("- **Critic set** (`eval/critic_set.jsonl`): 20 drafts labelled good/bad by a team member (wrong number, "
        "missing caveat, wrong language, promise, outdated number, PII, injection echo). Agreement = critic's "
        "answer/revise decision matches the human label.")
    add("- **PII scan**: seeded secrets (OTP, account, ID, phone) searched in every response, audit record, "
        "referral bundle and stored message; answers also scanned with the PII detector.\n")
    add("## Summary\n")
    add("| Metric | Result |\n|---|---|")
    add(f"| Answer correctness (all checks) | {pct(s['passed'], s['cases'])} |")
    ev = s["eligibility"]
    add(f"| Eligibility accuracy, per scheme | {pct(ev['scheme_verdicts']['ok'], ev['scheme_verdicts']['n'])} |")
    add(f"| Eligibility accuracy, per rule | {pct(ev['rules']['ok'], ev['rules']['n'])} |")
    cons = s["language"]["cross_language"]
    add(f"| Same verdict across languages | {sum(v['same_verdicts'] for v in cons.values())}/{len(cons)} groups |")
    add(f"| Same numbers across languages | {sum(v['same_numbers'] for v in cons.values())}/{len(cons)} groups |")
    ci = s["citations"]
    add(f"| Citation validity (source exists) | {pct(ci['exist'], ci['citations'])} |")
    add(f"| Citation validity (in retrieval output) | {pct(ci['in_retrieval_output'], ci['citations'])} |")
    add(f"| Expected source cited | {pct(ci['expected_source_cited'], ci['cases_with_expectation'])} |")
    m = s["retrieval"]["configs"][1]
    add(f"| Retrieval hit@6, production config ({m['model']}) | {m['hit_at_6'] * 100:.1f}% strict, "
        f"{m['equivalent_hit_at_6'] * 100:.1f}% incl. same-content translation (MRR {m['mrr']:.2f}) |")
    rc = s["referral_confusion"]
    add(f"| Referral precision / recall | {rc['precision']:.2f} / {rc['recall']:.2f} |")
    add(f"| Avg questions per resolved case | {s['questions']['avg_questions_per_resolved_case']:.2f} |")
    add(f"| Repeated questions | {s['questions']['repeated_questions']} |")
    add(f"| Turns with more than 2 questions | {s['questions']['turns_over_two_questions']} |")
    add(f"| Critic agreement (threshold 0.8) | {s['critic']['critic (threshold 0.8)']['agreement'] * 100:.0f}% |")
    add(f"| PII leaks | {len(s['pii']['leaks'])} |")
    add(f"| Latency p50 / p95 | {s['latency_ms']['p50']:.0f} ms / {s['latency_ms']['p95']:.0f} ms |")
    add(f"| LLM calls / tokens per request | {s['llm']['calls_per_request']:.2f} / {s['llm']['tokens_per_request']:.0f} |\n")
    add("## Results by category\n")
    add("| Category | Passed |\n|---|---|")
    for k, v in s["by_category"].items():
        add(f"| {k} | {v['passed']}/{v['n']} |")
    add("\n## Referral confusion table\n")
    add("| | Labelled: refer | Labelled: answer |\n|---|---|---|")
    add(f"| System referred | {rc['tp']} | {rc['fp']} (over-referral) |")
    add(f"| System answered | {rc['fn']} (under-referral) | {rc['tn']} |\n")
    add("## Retrieval by language pair (hit@6)\n")
    add("Strict: the expected document itself is in the top 6. In brackets: hits that count a translated "
        "summary of the same document (e.g. GL-PEN-01-KN for GL-PEN-01) as correct, since it carries the same "
        "rules in the citizen's language.\n")
    cfgs = [c for c in s["retrieval"]["configs"] if "per_pair" in c]
    pairs = sorted({p for c in cfgs for p in c["per_pair"]})
    add("| Pair | " + " | ".join(c["model"] for c in cfgs) + " |")
    add("|---|" + "---|" * len(cfgs))
    for p in pairs:
        cells = []
        for c in cfgs:
            v = c["per_pair"].get(p)
            cells.append(f"{v['hits']}/{v['n']} ({v['equivalent']})" if v else "n/a")
        add(f"| {p} | " + " | ".join(cells) + " |")
    add("| **all** | " + " | ".join(f"**{c['hit_at_6'] * 100:.0f}%** ({c['equivalent_hit_at_6'] * 100:.0f}%), MRR {c['mrr']:.2f}"
                                    for c in cfgs) + " |")
    for c in s["retrieval"]["configs"]:
        if "error" in c:
            add(f"\n`{c['model']}` was not evaluated: {c['error']}")
    add("\n## Critic configurations\n")
    add("| Configuration | Agreement with human labels | Flagged good drafts | Missed bad drafts |\n|---|---|---|---|")
    for name, v in s["critic"].items():
        conf = v["confusion"]
        add(f"| {name} | {v['agreement'] * 100:.0f}% | {conf.get('flagged/good', 0)} | {conf.get('passed/bad', 0)} |")
    add(f"\nCritic revisions triggered during the end-to-end run: {s['critic_revisions_in_run']}.\n")
    add("## Language fidelity\n")
    add("Automatic script check (reply written in the expected script; scheme names in brackets and source IDs ignored):\n")
    add("| Reply language | Script match |\n|---|---|")
    for k, v in sorted(s["language"]["script_match"].items()):
        add(f"| {k} | {v['ok']}/{v['n']} |")
    add("\nNumbers and verdicts for the same facts asked in en/hi/kn/ta:\n")
    for g, v in cons.items():
        add(f"- `{g}`: same verdicts **{v['same_verdicts']}**, same numbers **{v['same_numbers']}** "
            f"({', '.join(mm['id'] for mm in v['members'])}; numbers {v['members'][0]['numbers']})")
    add("\nHuman check: replies are template-based for structured answers, and the templates were reviewed by "
        "the team. Fluency of free-text (retrieved) answers still needs a native-speaker sample check per language; "
        "record it in `docs/data_card.md` when done.\n")
    add("## PII\n")
    add(f"Scanned {s['pii']['audit_records']} audit records, {s['pii']['bundles']} referral bundles and "
        f"{s['pii']['messages']} stored messages plus all responses. Leaks found: **{len(s['pii']['leaks'])}**.\n")
    add("## Failures\n")
    if not s["failures"]:
        add("None.")
    for f in s["failures"]:
        add(f"- **{f['id']}**: {', '.join(f['failed_checks'])}")
    add("\n## What the numbers say\n")
    best = max(cfgs, key=lambda c: (c["hit_at_6"], c["mrr"]))
    add(f"- **Best retrieval configuration on this set: {best['model']}** ({best['hit_at_6'] * 100:.0f}% strict hit@6). "
        f"The deployed default is `{s['mode']['embedding']}` with scheme boost; switch `EMBEDDING_MODEL` if a "
        f"larger model wins and its CPU latency is acceptable.")
    weak = sorted({p for c in cfgs[:2] for p, v in c["per_pair"].items() if v["rate"] < 0.5})
    if weak:
        add(f"- **Weak pairs for the default model: {', '.join(weak)}.** Kannada/Tamil questions usually retrieve the "
            "Kannada/Tamil summary of a guideline rather than the English original. This is why eligibility, "
            "documents and dates never depend on retrieval: they come from the rule tables and SQLite tools, and "
            "retrieval only supplies the citation, which is pinned to the exact guideline section by code.")
    add("- **Critic**: scoping evidence per scheme and flagging superseded values is what catches a limit borrowed "
        "from another scheme or an old limit/date (compare the scoped and unscoped rows). Lowering the threshold "
        "to 0.5 lets more wrong numbers through; no critic misses every bad draft.")
    add("- **Language handling**: structured answers are composed natively in each language from tool output "
        "(no translation step), so numbers, dates and verdicts are identical across languages (see the "
        "cross-language check). Free-text answers use retrieved passages in the citizen's language when one exists.")
    add("- **Caveat**: these cases were written by the team and used during development, so they measure regressions "
        "more than generalisation. Judges' unseen requests are the real test.")
    (HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
