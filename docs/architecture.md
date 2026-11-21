# Architecture and design decisions

This document explains *why* SchemeSathi is built the way it is. Every member should be able to answer the
questions in section 4 without notes.

## 1. Request lifecycle (`POST /ask`)

| Step | Node (`app/graph.py`) | What happens | Code or LLM |
|---|---|---|---|
| 1 | `guard` | Load or create a conversation owned by the signed-in account or guest session. Use the linked citizen profile only if `consent_given = Y`. Redact PII from the message before storage. | code |
| 2 | `classify` | Script → language (Unicode ranges). PII, fraud, bribe, another person's data, secret requests and prompt injection come from regex and lexicons. Intent, sentiment and attributes come from the LLM as validated JSON, or heuristics in mock mode. Safety intents from code always win. A number from the LLM is accepted only if it appears in the message. | code + optional LLM |
| 3 | route | Plain `if` statements over the classifier output (refuse, out of scope, referral, action, eligibility, knowledge). | code |
| 4a | `eligibility` | Merge attributes: conversation memory, then consenting profile, then the message. Run the rule engine for every scheme. Ask at most 2 questions for attributes the rules in play still need. Otherwise compose the verdict text. | code |
| 4b | `knowledge` | Documents → `get_required_documents`. Dates/status → `get_scheme` (circulars applied). Application status → `get_applications`. "Tell me about X" → rules in force. Anything else → free-text retrieval. | code (+ LLM for free text) |
| 4c | `action` | Plan a booking, cancellation, reminder or draft and write a **pending** row in `actions`. Nothing executes. | code |
| 5 | `retrieve` | Top-k search across languages, then **pin** each section the draft cites (fetched by `source_id` + section number), so citations always point to the exact clause. | code |
| 6 | `critic` | Score the draft. One `revise` loop is allowed, then answer or refer. | code |
| 7 | `policy` | Annex A.4 referral rules over intent flags, critic output, verdicts and tool failures. | code |
| 8 | `referral` | Queue, priority and SLA from the policy registry; Annex D bundle (redacted); citizen message that promises nothing. | code |
| 9 | `finalize` | Readable citations, PII warning, conversation memory, audit record. | code |

Actions execute only in `POST /actions/{id}/confirm`, which checks the signed-in citizen, ownership, expiry and status,
runs the executor, then reads the row back to verify it. A second call returns the stored result.

## 2. Key decisions and trade-offs

**Eligibility is code over rule rows, never the model.** The guide's disqualification list makes this
mandatory, and it is also the only way to get boundaries right: ₹1,50,000 passes, ₹1,50,001 fails, and the
age on `as_of_date` is computed from the date of birth. Amendments are just new rule rows with a later
`effective_from` and an earlier row's `valid_until`. This is how "a newer amendment replaces only the clause
it names" is implemented.

**Structured answers are written from templates, not by the LLM.** The guide's hardest multilingual
requirement is that "numbers, dates and amounts must be identical across languages". If a 7B model wrote
Kannada or Tamil answers, it would sometimes rewrite or drop numbers. Templates filled from tool output make
that impossible: the eval's cross-language check shows the same verdict and the same numbers in en/hi/kn/ta.
The cost is less natural phrasing, which we accept for a welfare service. The LLM writes only free-text
answers (for example "when is the pension credited?"), and the critic checks those.

**Language handling: native, no translation step.** The question is embedded as-is with a multilingual model (e5-small by default; bge-m3 measured better for kn/ta, see the report).
The answer is composed natively in the reply language. We measured retrieval per language pair. Hindi→English
works well. Kannada→English and Tamil→English are weak with e5-small, which mostly retrieves the
Kannada/Tamil summary of the same guideline. That is still the right content, and the report counts both.
Because eligibility, documents and dates come from SQLite tools rather than retrieval, this weakness does not
reach the verdicts. If a larger model wins the comparison in `eval/report.md`, change `EMBEDDING_MODEL`.
A translate-first design (for example IndicTrans2) would add a model, latency and a new source of number
errors for little gain on structured answers.

**The critic is deterministic.** Each check is precise:
- every number must appear in evidence for the scheme the sentence names, so a limit cannot be "supported"
  by another scheme's rule;
- a value replaced by an amendment (the old income limit, the old last date) must not be stated as current;
- eligibility answers must carry the "department decides" caveat;
- the reply must be in the expected script;
- no PII and no promise phrases.

A 7B model judging groundedness would be slower and less reliable than these checks. The critic set shows
the value of scoping and superseded-value detection by comparing configurations. One revision rebuilds the
draft from authority 1–3 sources only. If it still fails, the case is referred.

**One supervisor graph, not many LLM agents.** Every routing decision is a policy from Annex A, so it should
be predictable and unit-testable. LangGraph gives an explicit, inspectable state machine: the route appears
in every audit record. Adding more LLM agents would add cost and failure modes without meeting any extra
requirement.

**Circular effects are parsed in code at ingest.** "Extended from X to Y", "closed for new applications with
effect from D" and "income limit raised from A to B" are recognised by patterns over ISO dates and ₹ amounts
(`kb/effects.py`). Date changes apply immediately, which is what the judges' live amendment test needs.
A limit change that the rule rows do not yet reflect makes the verdict `verify_with_officer` and triggers a
referral (R9), until someone loads the new rule row with the loader.

**Source precedence (Annex A.2)** is enforced in four places:
- the scheme status logic applies circulars (level 2) over the scheme row;
- the rule engine detects amendments newer than the rule rows;
- the critic rejects drafts that rely on a grievance or FAQ (level 4) when a guideline or circular for the
  same scheme was retrieved;
- authority-5 content (forwarded messages) is never cited.

**Privacy.**
- Profile lookup uses the citizen linked to the authenticated account and requires consent.
- Questions about another person get a refusal that does not reveal whether that person exists.
- PII is redacted before storage, in bundles, in audit records and in answers.
- The centre phone numbers are treated as PII and never shown.
- Sensitive attributes (category, disability) are asked only when a scheme in focus needs them, and are not
  echoed back in discovery summaries.

## 3. Thresholds (all in the policy registry, all cited)

| Parameter | Value | Why |
|---|---|---|
| `critic_min_groundedness` | 0.8 | With 0.5, wrong-number drafts pass (critic table in the report) |
| `max_questions_per_turn` | 2 | Guide R5; keeps turns short on a phone |
| `critic_max_revisions` | 1 | Guide R7 |
| `appointment_min_lead_hours` | 24 | Gives centres time to prepare; POL-APPT-01 §2 |
| `action_expiry_minutes` | 30 | A stale proposal must not be confirmed later by accident |
| `referral_sla_working_days_*` | 1 / 2 / 5 | Urgent / high / normal, POL-GRV-01 §3 |
| `application_processing_target_days` | 45 | Beyond this, a status question becomes a delay referral |
| `retrieval_top_k` | 6 | Enough for one guideline section plus its circulars |

## 4. Questions to be ready for

1. *Why not let the LLM decide eligibility?* Boundaries, dates and amendments need exact arithmetic and
   traceability. The rule-by-rule output is the audit trail.
2. *Where does language handling happen?* Detection is code (Unicode). Retrieval is native multilingual
   embeddings. Answers are native templates per language. Kannada/Tamil cross-lingual retrieval is weaker,
   which is why verdicts never depend on retrieval.
3. *What happens when the judges ingest an amendment?* It is chunked and embedded, and its effect is parsed
   and stored in `doc_effects`. The next request uses it. Show `CIR-2026-020` live.
4. *How do you stop the LLM from confirming an action?* Executors are reachable only from the confirm
   endpoint, which needs the owner's header. Typing "yes confirm" gets a reminder to press the button.
5. *How do you avoid over-referral?* Discovery lists do not refer for a provisional scheme. The eval's
   confusion table reports both over- and under-referral.
6. *What would you change with more time?* Run the eval in Ollama mode, have native speakers review the
   kn/ta templates, add a stronger cross-lingual embedding model if latency allows, deliver reminders, and
   model centre capacity.
