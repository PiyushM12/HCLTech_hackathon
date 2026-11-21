"""Extract the structured effect of a circular or amendment from its text (R9, R14).

This is deliberately plain code over explicit patterns: a newly ingested amendment that
extends a last date or closes a scheme must change the answer immediately and
predictably, without trusting a model to read dates. Anything it cannot classify stays a
plain retrievable document."""
from __future__ import annotations

import re
from typing import Any

ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
INR = re.compile(r"(?:₹|rs\.?\s*|inr\s*)\s?(\d{1,3}(?:,\d{2,3})+|\d+)(?:\s*(lakh|lac|लाख|ಲಕ್ಷ|லட்சம்))?", re.I)
ACRES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:acres?|एकड़|एकड|ಎಕರೆ|ஏக்கர்)", re.I)
PERCENT = re.compile(r"(\d{1,3})\s*%")
YEARS = re.compile(r"(\d{1,3})\s*(?:years?|वर्ष|साल|ವರ್ಷ|வயது)", re.I)

DEADLINE_WORDS = re.compile(r"last date|deadline|अंतिम तिथि|आखिरी तारीख|अंतिम तारीख|ಕೊನೆಯ ದಿನಾಂಕ|கடைசி தேதி|கடைசி நாள்", re.I)
EXTEND_WORDS = re.compile(r"extend|extension|बढ़ा|बढा|ವಿಸ್ತರ|நீட்டி", re.I)
NO_EXTENSION = re.compile(r"no extension|not be extended|will not be extended|नहीं बढ़ाई|ವಿಸ್ತರಿಸಲಾಗುವುದಿಲ್ಲ|நீட்டிப்பு இல்லை|நீட்டிக்கப்படாது", re.I)
CLOSURE = re.compile(r"closed for (?:all )?new applications|scheme (?:is|stands) (?:closed|discontinued)|discontinued with effect|नए आवेदन बंद|योजना बंद", re.I)
LIMIT_WORDS = re.compile(
    r"income limit|income ceiling|land ceiling|land limit|age limit|eligib|limit in section|"
    r"आय सीमा|आय की सीमा|भूमि सीमा|पात्रता|ಆದಾಯ ಮಿತಿ|ಅರ್ಹತೆ|ಭೂ ಮಿತಿ|வருமான வரம்பு|தகுதி|நில வரம்பு", re.I)
CHANGE_WORDS = re.compile(
    r"raised|revised|increased|reduced|lowered|changed|amended|replaced|from .{1,40} to |"
    r"बढ़ा|बढा|संशोधित|बदल|घटा|ಹೆಚ್ಚಿಸ|ಪರಿಷ್ಕ|ಬದಲ|ಇಳಿಸ|உயர்த்த|திருத்த|மாற்ற|குறைக்க", re.I)
EXTENDED_TO = re.compile(r"extended\s+(?:from\s+20\d{2}-\d{2}-\d{2}[^.\n]{0,40}?\s+)?(?:up\s+)?to\s+(20\d{2}-\d{2}-\d{2})", re.I)
FX_DATE = re.compile(r"(?:with effect from|effective from|from)\s+(20\d{2}-\d{2}-\d{2})", re.I)


def _inr_value(num: str, unit: str | None) -> int:
    n = float(num.replace(",", ""))
    if unit:
        n *= 100000
    return int(round(n))


def numeric_values(text: str) -> list[dict[str, Any]]:
    """Limit-like values mentioned in sentences that talk about limits/eligibility."""
    out: list[dict[str, Any]] = []
    for sentence in re.split(r"(?<=[.।\n])\s*", text):
        if not (LIMIT_WORDS.search(sentence) and CHANGE_WORDS.search(sentence)):
            continue
        for m in INR.finditer(sentence):
            out.append({"kind": "inr", "value": _inr_value(m.group(1), m.group(2))})
        for m in ACRES.finditer(sentence):
            out.append({"kind": "acres", "value": float(m.group(1))})
        for m in PERCENT.finditer(sentence):
            out.append({"kind": "percent", "value": int(m.group(1))})
        for m in YEARS.finditer(sentence):
            out.append({"kind": "years", "value": int(m.group(1))})
    uniq = {(v["kind"], v["value"]): v for v in out}
    return list(uniq.values())


def extract_effects(meta: dict[str, Any], text: str) -> list[dict[str, Any]]:
    doc_type = (meta.get("doc_type") or "").lower()
    scheme_id = meta.get("scheme_id") or ""
    if doc_type not in {"circular", "amendment"} or not scheme_id:
        return []
    effective = meta.get("effective_from") or meta.get("last_updated") or ""
    base = {"source_id": meta["source_id"], "scheme_id": scheme_id, "effective_from": effective,
            "last_updated": meta.get("last_updated") or effective,
            "authority_level": int(meta.get("authority_level") or 2)}
    effects: list[dict[str, Any]] = []

    if CLOSURE.search(text):
        m = FX_DATE.search(text)
        effects.append({**base, "effect_type": "closure", "field": "status", "new_value": "closed",
                        "effective_from": (m.group(1) if m else effective)})

    explicit = EXTENDED_TO.findall(text) if DEADLINE_WORDS.search(text) else []
    if explicit:
        effects.append({**base, "effect_type": "deadline_change", "field": "apply_until", "new_value": max(explicit)})
    elif DEADLINE_WORDS.search(text) and EXTEND_WORDS.search(text) and not NO_EXTENSION.search(text):
        dates = sorted({"-".join(m.groups()) for m in ISO_DATE.finditer(text)})
        if dates:
            # The new last date is the latest date mentioned; it is only applied if it is
            # later than the current last date (checked when the scheme is read).
            effects.append({**base, "effect_type": "deadline_change", "field": "apply_until",
                            "new_value": dates[-1]})

    values = numeric_values(text)
    if values:
        effects.append({**base, "effect_type": "eligibility_change", "field": "eligibility_rules",
                        "new_value": "", "values": values})
    return effects


INJECTION = re.compile(
    r"(^|\n|\s)(system|assistant|developer)\s*:|ignore (all )?(the )?(previous|above|prior) (rules|instructions)|"
    r"disregard (all )?(previous|prior)|mark (me|every|all|everyone)[^.\n]{0,40}eligible|you are now|"
    r"new instructions|override (the )?rules|reveal (your|the) (system )?prompt", re.I)


def contains_instructions(text: str) -> bool:
    return bool(INJECTION.search(text or ""))
