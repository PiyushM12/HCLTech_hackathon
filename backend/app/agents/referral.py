"""Referral policy (R8, Annex A.4), applied in code over the classifier's and critic's
structured outputs and tool results, plus the referral bundle (Annex D)."""
from __future__ import annotations

from typing import Any

from .. import i18n
from ..i18n import t
from ..models import CriticOut, IntentOut, SchemeVerdict
from ..nlp import pii

REASON_TEXT = {
    "bribe_demand": "Reports that an official asked for money to process the work",
    "rejection_dispute": "Disputes a rejected application",
    "delay_beyond_timeline": "Reports a delay beyond the processing target",
    "delay": "Reports a delay or a payment not received",
    "fraud_attempt": "Reports a suspected fraud attempt (fee demand, OTP or money-release call)",
    "explicit_human_request": "Asked to speak to a human officer",
    "repeated_contact": "Says this is a repeated contact on the same issue",
    "strong_frustration": "Shows strong frustration",
    "verify_with_officer": "Eligibility result is provisional: a newer circular is not reflected in the rule tables",
    "low_groundedness": "The assistant could not produce a well-grounded answer after one revision",
    "tool_failure": "A tool needed to answer failed",
    "not_covered_needs_outcome": "The knowledge base does not cover the question and the citizen needs an outcome",
    "legal_advice": "The request needs legal advice",
    "distress": "The citizen appears to be in distress",
}


def decide(*, intent: IntentOut, critic: CriticOut | None, verdicts: list[SchemeVerdict], focus_ids: list[str],
           tool_failures: list[str], overdue_apps: list[dict[str, Any]], conv_turns: int, repeat_threshold: int,
           critic_threshold: float) -> list[str]:
    reasons: list[str] = []
    f = set(intent.flags)
    if intent.type == "fraud_report":
        reasons.append("fraud_attempt")
    if intent.type == "grievance":
        if "bribe_demand" in f:
            reasons.append("bribe_demand")
        if "rejection_dispute" in f:
            reasons.append("rejection_dispute")
        if overdue_apps:
            reasons.append("delay_beyond_timeline")
        elif "delay" in f:
            reasons.append("delay")
        if "legal_advice" in f:
            reasons.append("legal_advice")
    if "explicit_human_request" in f:
        reasons.append("explicit_human_request")
    if "repeated_contact" in f or (intent.sentiment == "frustrated" and conv_turns + 1 >= repeat_threshold):
        reasons.append("repeated_contact")
    if intent.sentiment == "frustrated" and "repeated_contact" in reasons:
        reasons.append("strong_frustration")
    if intent.urgency == "urgent":
        reasons.append("distress")
    if any(v.verdict == "verify_with_officer" for v in verdicts if v.scheme_id in focus_ids):
        reasons.append("verify_with_officer")
    if critic and critic.decision == "refer":
        reasons.append("low_groundedness")
    if tool_failures:
        reasons.append("tool_failure")
    if intent.type == "grievance" and not reasons:
        reasons.append("explicit_human_request" if "explicit_human_request" in f else "delay")
    return list(dict.fromkeys(reasons))


def queue_and_priority(reasons: list[str], intent: IntentOut) -> tuple[str, str]:
    if "fraud_attempt" in reasons:
        queue = "fraud_desk"
    elif {"bribe_demand", "rejection_dispute", "delay_beyond_timeline", "delay", "repeated_contact"} & set(reasons) \
            or intent.type == "grievance":
        queue = "grievance"
    else:
        queue = "department_helpdesk"
    if "distress" in reasons:
        priority = "urgent"
    elif {"bribe_demand", "fraud_attempt", "strong_frustration"} & set(reasons):
        priority = "high"
    elif {"verify_with_officer", "rejection_dispute", "delay_beyond_timeline", "explicit_human_request"} & set(reasons):
        priority = "normal"
    else:
        priority = "low" if reasons == ["low_groundedness"] else "normal"
    return queue, priority


def sla_parameter(priority: str) -> str:
    return {"urgent": "referral_sla_working_days_urgent", "high": "referral_sla_working_days_high"}.get(
        priority, "referral_sla_working_days_normal")


def build_bundle(*, reasons: list[str], queue: str, priority: str, intent: IntentOut, message_redacted: str,
                 evidence: list[dict[str, Any]], attempted_answer: str, unresolved: list[str], conversation_id: str,
                 citizen_id: str, language: str, as_of: str, sla_days: int, trace_id: str,
                 attributes: dict[str, Any]) -> dict[str, Any]:
    summary = "; ".join(REASON_TEXT.get(r, r) for r in reasons) + "."
    excerpt = message_redacted.strip().replace("\n", " ")
    if len(excerpt) > 280:
        excerpt = excerpt[:277] + "..."
    bundle = {
        "queue": queue, "priority": priority, "intent": intent.type, "urgency": intent.urgency,
        "sentiment": intent.sentiment, "referral_reasons": reasons,
        "citizen_summary": f"{summary} Citizen wrote (redacted): \"{excerpt}\"",
        "citizen_language": language, "citizen_id": citizen_id, "conversation_id": conversation_id,
        "trace_id": trace_id, "as_of_date": as_of,
        "known_attributes": {k: v for k, v in attributes.items() if k not in {"category", "is_disabled", "disability_percent"}},
        "evidence": evidence, "attempted_answer": attempted_answer, "unresolved_questions": unresolved,
        "sla_working_days": sla_days, "pii_redacted": True,
    }
    return pii.redact_obj(bundle)


def citizen_message(*, reasons: list[str], queue: str, sla: int, lang: str, rid: str) -> str:
    qlabel = t(f"q_{queue}", lang)
    if "fraud_attempt" in reasons:
        body = t("ref_fraud", lang, queue=qlabel, sla=sla)
    elif {"bribe_demand", "rejection_dispute", "delay_beyond_timeline", "delay", "repeated_contact"} & set(reasons):
        rule_line = t("bribe_rule_line", lang) if "bribe_demand" in reasons else ""
        body = t("ref_grievance", lang, rule_line=rule_line, queue=qlabel, sla=sla)
    elif reasons == ["explicit_human_request"]:
        body = t("ref_human", lang, queue=qlabel, sla=sla)
    else:
        body = t("ref_generic", lang, queue=qlabel, sla=sla)
    return f"{body}\n{t('ref_id_line', lang, rid=rid)}"


def unresolved_questions(reasons: list[str], overdue: list[dict[str, Any]], verdicts: list[SchemeVerdict],
                         apps: list[dict[str, Any]], target_days: int) -> list[str]:
    out = []
    for a in overdue:
        out.append(f"Why is {a['application_id']} still '{a['status']}' beyond the {target_days}-day target?")
    if "rejection_dispute" in reasons:
        for a in apps:
            if a["status"] == "rejected":
                out.append(f"Review the rejection of {a['application_id']} (remarks: {a.get('remarks') or 'none'}).")
        if not any(a["status"] == "rejected" for a in apps):
            out.append("Identify the rejected application and review the reason.")
    if "bribe_demand" in reasons:
        out.append("Investigate the reported demand for money and assure the citizen of the no-fee rule.")
    if "fraud_attempt" in reasons:
        out.append("Check whether the citizen has paid or shared an OTP; advise bank blocking if so.")
    for v in verdicts:
        if v.verdict == "verify_with_officer":
            srcs = ", ".join(sorted({c.get("source_id", "") for c in v.conflicts if c.get("source_id")}))
            out.append(f"Confirm eligibility for {v.scheme_id} under {srcs or 'the latest circular'}.")
    if "explicit_human_request" in reasons and not out:
        out.append("Citizen asked to speak to an officer; call back and understand the issue.")
    return out


def verdict_evidence(verdicts: list[SchemeVerdict]) -> list[dict[str, Any]]:
    return [{"tool": "check_eligibility", "output": {"scheme_id": v.scheme_id, "verdict": v.verdict,
                                                     "conflicts": v.conflicts}} for v in verdicts]


__all__ = ["decide", "queue_and_priority", "build_bundle", "citizen_message", "sla_parameter",
           "unresolved_questions", "verdict_evidence", "i18n"]
