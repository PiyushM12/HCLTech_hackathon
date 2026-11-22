"""Critic (R7). Checks every draft and returns answer | revise | refer.

The checks are code, because each one is precise and must not depend on a 7B model:
* groundedness: every number, amount and date in the draft must appear in authoritative
  evidence (tool output, sources of authority 1-3, or what the citizen said). Numbers found
  only in FAQs/grievances (authority 4) count as unsupported (Annex A.2 precedence).
* precedence: a draft built on a grievance/FAQ while a guideline/circular for the same
  scheme was retrieved is sent back for revision.
* coverage: eligibility verdicts must carry the "department decides" caveat; factual
  answers must have citations.
* language fidelity: the reply must be in the expected script.
* PII: no phone, ID, account number or OTP may appear.
* promise risk: phrases that promise a benefit are not allowed."""
from __future__ import annotations

import re
from typing import Any

from .. import i18n
from ..models import CriticOut
from ..nlp import lang as langmod
from ..nlp import pii

PROMISE = {
    "en": [r"\byou will (definitely |surely )?(get|receive)\b", r"\bguarantee", r"\bdefinitely (get|eligible)",
           r"\bwill be approved\b", r"\b100\s?%\s*(sure|eligible)", r"\byou are eligible\b", r"\bsurely\b"],
    "hi": ["ज़रूर मिलेगी", "जरूर मिलेगी", "ज़रूर मिलेगा", "जरूर मिलेगा", "पक्का", "गारंटी", "निश्चित रूप से मिलेगी",
           "मंज़ूर हो जाएगा", "आप पात्र हैं"],
    "kn": ["ಖಂಡಿತ ಸಿಗುತ್ತದೆ", "ಖಚಿತವಾಗಿ ಸಿಗುತ್ತದೆ", "ಗ್ಯಾರಂಟಿ", "ಮಂಜೂರಾಗುತ್ತದೆ"],
    "ta": ["நிச்சயம் கிடைக்கும்", "உறுதியாக கிடைக்கும்", "உத்தரவாதம்", "அனுமதிக்கப்படும்"],
    "hinglish": [r"\bpakka\b", r"zaroor milega", r"zaroor milegi", r"\bguarantee", r"approve ho jayega"],
}
INJECTION_ECHO = re.compile(r"system\s*:|ignore (all )?previous|mark (every|all)[^.]*eligible", re.I)
CAVEAT_MARKERS = {
    "en": ["final decision", "department decides"], "hi": ["अंतिम निर्णय", "निर्णय विभाग"],
    "kn": ["ಅಂತಿಮ ನಿರ್ಧಾರ", "ಇಲಾಖೆ ನಿರ್ಧರಿಸುತ್ತದೆ"], "ta": ["இறுதி முடிவ", "துறையே முடிவு"],
    "hinglish": ["antim faisla", "faisla vibhag"],
}
NUM = re.compile(r"(?<![A-Z\-])(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)")
DMY = re.compile(r"\b(\d{2})-(\d{2})-(20\d{2})\b")
ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})(?!\d)")
ID_TOKEN = re.compile(r"\b(?:[A-Z]{2,4}-)+[A-Z0-9]+(?:-[A-Z0-9]+)*\b|\bC\d{4}\b|\bAPP-[\w-]+|\bACT-\d+|\bRF-\d+")


def _numbers(text: str) -> set[str]:
    text = ID_TOKEN.sub(" ", text or "")
    out: set[str] = set()
    for m in DMY.finditer(text):
        out.add(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")
    text = DMY.sub(" ", text)
    for m in ISO.finditer(text):
        out.add(m.group(0))
    text = ISO.sub(" ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)  # clock times are slot details, checked by the action tool
    for m in NUM.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        out.add(f"{v:g}")
    return out


def _evidence_numbers(evidence: list[str]) -> set[str]:
    nums: set[str] = set()
    for e in evidence:
        nums |= _numbers(e)
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:lakh|लाख|ಲಕ್ಷ|லட்சம்)", e or "", re.I):
            nums.add(f"{float(m.group(1)) * 100000:g}")
    return nums


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.।!?])\s+|\n", text or "") if s.strip()]


def review(*, draft: dict[str, Any], lang: str, evidence_authoritative: list[str], evidence_historical: list[str],
           retrieved: list[dict[str, Any]], answer_kind: str, has_verdict: bool, threshold: float,
           revisions: int, max_revisions: int, evidence_scoped: dict[str, list[str]] | None = None,
           superseded: dict[str, set[str]] | None = None, current: dict[str, set[str]] | None = None,
           citizen_values: list[str] | None = None, schemes: list[dict[str, Any]] | None = None) -> CriticOut:
    """`evidence_authoritative` is evidence that is not tied to one scheme; `evidence_scoped` maps
    scheme_id -> evidence for that scheme. A number in a sentence that names a scheme must be
    supported by general evidence or by *that* scheme's evidence, so a limit belonging to another
    scheme cannot "support" it. `superseded` holds values replaced by an amendment (old limits,
    old last dates); stating one as current is flagged (Annex A.2). Values the citizen gave
    (`citizen_values`) are always allowed."""
    from ..nlp import extract  # local import: keeps the critic importable on its own
    text = draft.get("text") or ""
    issues: list[str] = []

    # 1. groundedness over numbers, scoped per scheme mentioned in each sentence
    gen = _evidence_numbers(evidence_authoritative + list(draft.get("evidence") or []))
    hist = _evidence_numbers(evidence_historical)
    scoped = {k: _evidence_numbers(v) for k, v in (evidence_scoped or {}).items()}
    all_scoped = set().union(*scoped.values()) if scoped else set()
    citizen = _evidence_numbers(citizen_values or [])
    sup = superseded or {}
    cur = current or {}
    claimed: list[str] = []
    unsupported: list[str] = []
    outdated: list[str] = []
    for sent in _sentences(text):
        nums = _numbers(sent)
        if not nums:
            continue
        named = extract.mentioned_schemes(sent, schemes) if schemes else []
        pool = gen | (set().union(*(scoped.get(s, set()) for s in named)) if named else all_scoped)
        scope = named or list(sup)
        for n in sorted(nums):
            claimed.append(n)
            if n in citizen:
                continue
            stale = [s for s in scope if n in sup.get(s, set()) and n not in cur.get(s, set())]
            # "extended from <old> to <new>" may mention the old value next to the current one
            if stale and not any(m in cur.get(s, set()) for s in stale for m in nums if m != n):
                outdated.append(n)
                issues.append(f"number {n} was replaced by a newer amendment but is stated as current")
                continue
            if n not in pool:
                unsupported.append(n)
                issues.append(f"number {n} is supported only by a historical FAQ/grievance" if n in hist
                              else f"number {n} is not in any tool result or authoritative source for this scheme")
    bad_n = len(unsupported) + len(outdated)
    groundedness = 1.0 if not claimed else (len(claimed) - bad_n) / len(claimed)

    # 2. precedence: built on authority-4 content while authority 1-2 content for the scheme exists
    used = draft.get("used_hits") or []
    for h in used:
        if int(h["meta"].get("authority_level") or 5) >= 4:
            scheme = h["meta"].get("scheme_id")
            better = [r for r in retrieved if int(r["meta"].get("authority_level") or 5) <= 2
                      and (not scheme or r["meta"].get("scheme_id") in (scheme, ""))]
            if better:
                issues.append(f"answer relies on {h['source_id']} ({h['meta'].get('doc_type')}) although "
                              f"{better[0]['source_id']} has higher authority")
                groundedness = min(groundedness, 0.5)

    # 3. citations and caveat
    if answer_kind in {"eligibility", "discovery", "documents", "status", "scheme_info", "general_llm",
                       "general_extractive"} and not draft.get("cites"):
        issues.append("factual answer without a citation")
        groundedness = min(groundedness, 0.6)
    coverage = "complete"
    if has_verdict:
        markers = CAVEAT_MARKERS.get(i18n.L(lang), CAVEAT_MARKERS["en"])
        if not any(m.lower() in text.lower() for m in markers):
            issues.append("eligibility answer is missing the 'department decides' caveat")
            coverage = "partial"
    if not text.strip():
        coverage = "missing"

    # 4. language fidelity (ignore English scheme names in brackets and source IDs)
    stripped = re.sub(r"\([^)]*\)", " ", ID_TOKEN.sub(" ", text))
    fidelity = "good"
    share = langmod.script_share(stripped, i18n.L(lang))
    if text.strip() and ((lang in {"hi", "kn", "ta"} and share < 0.5) or (lang in {"en", "hinglish"} and share < 0.7)):
        fidelity = "poor"
        issues.append(f"reply is not in the expected script for '{lang}' (share {share:.2f})")

    # 5. PII and secrets
    found = pii.detect(text)
    pii_risk = "high" if found else "none"
    if found:
        issues.append(f"draft contains PII: {found}")

    # 6. promise risk and injection echo
    promise = "none"
    for pat in PROMISE.get(i18n.L(lang), []) + PROMISE["en"]:
        if re.search(pat, text, re.I):
            promise = "high"
            issues.append(f"promise phrase: '{pat}'")
            break
    if INJECTION_ECHO.search(text):
        promise = "high"
        issues.append("draft echoes an instruction found in untrusted text")

    bad = (groundedness < threshold or coverage != "complete" or fidelity == "poor" or pii_risk != "none"
           or promise != "none")
    if not bad:
        decision = "answer"
    elif revisions < max_revisions:
        decision = "revise"
    else:
        # after the allowed revision: PII is redacted by the finaliser; anything else is referred
        still_bad = (groundedness < threshold or coverage != "complete" or fidelity == "poor" or promise != "none")
        decision = "refer" if still_bad else "answer"
    return CriticOut(groundedness=round(groundedness, 2), coverage=coverage, language_fidelity=fidelity,
                     pii_risk=pii_risk, promise_risk=promise, decision=decision, revisions=revisions, issues=issues)
