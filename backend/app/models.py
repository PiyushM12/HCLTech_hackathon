"""Pydantic v2 models for the API contract (Section 6 of the participant guide) and for
structured LLM output."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field

Lang = Literal["hi", "en", "kn", "ta", "hinglish"]
ReplyLang = Literal["hi", "en", "kn", "ta"]
IntentType = Literal[
    "discovery", "eligibility_check", "documents", "status_deadline", "service_visit",
    "application_draft", "grievance", "fraud_report", "out_of_scope",
]
AnswerType = Literal[
    "answered", "clarification_needed", "confirmation_needed", "action_completed",
    "referred", "not_found", "refused", "out_of_scope",
]
Verdict = Literal["appears_eligible", "not_eligible", "need_more_information", "verify_with_officer"]


# ---------------------------------------------------------------- requests
def _normalize_as_of_date(value: str) -> str:
    return date.fromisoformat(value).isoformat() if value else value


AsOfDate = Annotated[str, AfterValidator(_normalize_as_of_date)]


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    channel: Optional[str] = "web"
    language: Optional[ReplyLang] = None
    as_of_date: Optional[AsOfDate] = None


class EligibilityRequest(BaseModel):
    attributes: dict[str, Any]
    scheme_ids: Optional[list[str]] = None
    as_of_date: Optional[AsOfDate] = None


class RecommendationRequest(BaseModel):
    attributes: dict[str, Any] | None = None
    as_of_date: AsOfDate | None = None
    conversation_id: str | None = None


# ---------------------------------------------------------------- shared pieces
class IntentOut(BaseModel):
    type: IntentType
    language: Lang
    script: Literal["devanagari", "kannada", "tamil", "latin", "mixed"] = "latin"
    urgency: Literal["low", "normal", "high", "urgent"] = "low"
    sentiment: Literal["positive", "neutral", "negative", "frustrated", "distressed"] = "neutral"
    attributes_mentioned: dict[str, Any] = Field(default_factory=dict)
    scheme_ids: list[str] = Field(default_factory=list)
    subject: Literal["self", "other"] = "self"
    pii_detected: bool = False
    tools_needed: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    flags: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    source_id: str
    doc_type: str
    title: str = ""
    section: str = ""
    scheme_id: Optional[str] = None
    language: str = "en"
    effective_from: Optional[str] = None
    last_updated: Optional[str] = None
    label: str = ""  # citizen-readable, e.g. "Source: GL-PEN-01, Section 3"


class RuleResult(BaseModel):
    rule_id: str
    attribute: str
    operator: str
    expected: str
    actual: Optional[Any] = None
    result: Literal["passed", "failed", "unknown"]
    rule_group: str = ""
    source_id: str = ""
    source_section: str = ""


class SchemeVerdict(BaseModel):
    scheme_id: str
    scheme_name: str = ""
    scheme_names: dict[str, str] = Field(default_factory=dict)
    verdict: Verdict
    rules: list[RuleResult] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    scheme_status: str = "open"
    can_apply_now: bool = True
    apply_until: Optional[str] = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    upcoming_changes: list[dict[str, Any]] = Field(default_factory=list)


class ToolCall(BaseModel):
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    ok: bool = True
    latency_ms: float = 0.0


class PendingAction(BaseModel):
    action_id: str
    action_type: Literal["draft_application", "book_appointment", "cancel_appointment", "set_reminder"]
    summary: str
    reminder: Optional[str] = None
    tier: int
    expires_at: str
    status: str = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class CriticOut(BaseModel):
    groundedness: float = Field(ge=0.0, le=1.0)
    coverage: Literal["complete", "partial", "missing"] = "complete"
    language_fidelity: Literal["good", "poor"] = "good"
    pii_risk: Literal["none", "low", "high"] = "none"
    promise_risk: Literal["none", "low", "high"] = "none"
    decision: Literal["answer", "revise", "refer"] = "answer"
    revisions: int = 0
    issues: list[str] = Field(default_factory=list)


class Question(BaseModel):
    attribute: str
    text: str
    reason: str = ""


class AskResponse(BaseModel):
    trace_id: str
    conversation_id: str
    answer_type: AnswerType
    language: Lang
    answer: str
    intent: Optional[IntentOut] = None
    citations: list[Citation] = Field(default_factory=list)
    tools_invoked: list[ToolCall] = Field(default_factory=list)
    eligibility: list[SchemeVerdict] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    pending_action: Optional[PendingAction] = None
    critic: Optional[CriticOut] = None
    conflicts_detected: list[dict[str, Any]] = Field(default_factory=list)
    referral_id: Optional[str] = None
    referral: Optional[dict[str, Any]] = None
    as_of_date: str


# ---------------------------------------------------------------- LLM structured output
class LLMClassification(BaseModel):
    """What the LLM is asked to return for R1. Validated; on failure we fall back to code."""
    intent: IntentType
    urgency: Literal["low", "normal", "high", "urgent"] = "low"
    sentiment: Literal["positive", "neutral", "negative", "frustrated", "distressed"] = "neutral"
    subject: Literal["self", "other"] = "self"
    attributes: dict[str, Any] = Field(default_factory=dict)
    scheme_hint: list[str] = Field(default_factory=list)
    wants_human: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
