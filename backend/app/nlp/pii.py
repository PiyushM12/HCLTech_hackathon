"""PII and secret detection / redaction (R11). Applied to the citizen's message before it is
stored or logged, to every draft answer (critic), to referral bundles and to audit records."""
from __future__ import annotations

import re
from typing import Any

_ACCOUNT_CTX = r"(?:account|a/c|acct|khata|khaata|खाता|ಖಾತೆ|கணக்கு|ac\s*no|bank)"
_OTP_WORDS = r"(?:otp|o\.t\.p|ओटीपी|ಒಟಿಪಿ|ஓடிபி|pin|पिन|cvv)"

PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # OTP / PIN in either order: "OTP is 482913", "482913 mera OTP hai"
    ("otp", re.compile(rf"{_OTP_WORDS}[^\d\n]{{0,20}}(\d{{4,8}})\b", re.I), "[OTP REDACTED]"),
    ("otp", re.compile(rf"\b(\d{{4,8}})\b[^\d\n]{{0,15}}{_OTP_WORDS}", re.I), "[OTP REDACTED]"),
    # 12-digit national ID (4-4-4 or contiguous)
    ("national_id", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"), "[ID REDACTED]"),
    # Phone numbers: Indian mobile, +91 forms and the synthetic 000-000-0000 format
    ("phone", re.compile(r"(?:\+91[\s-]?)?(?<!\d)[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[PHONE REDACTED]"),
    ("phone", re.compile(r"(?<!\d)\d{3}-\d{3}-\d{4}(?!\d)"), "[PHONE REDACTED]"),
    # Bank account: 9-18 digits near an account word, or any bare 13-18 digit run
    ("bank_account", re.compile(rf"{_ACCOUNT_CTX}[^\d\n]{{0,25}}(\d{{9,18}})\b", re.I), "[ACCOUNT REDACTED]"),
    ("bank_account", re.compile(r"(?<![\d,.])\d{13,18}(?![\d,.])"), "[ACCOUNT REDACTED]"),
    ("ifsc", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[IFSC REDACTED]"),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL REDACTED]"),
]


def detect(text: str) -> list[str]:
    found: list[str] = []
    for kind, pat, _ in PATTERNS:
        if pat.search(text or ""):
            found.append(kind)
    return sorted(set(found))


def redact(text: str) -> tuple[str, list[str]]:
    if not text:
        return text, []
    found: list[str] = []
    out = text
    for kind, pat, repl in PATTERNS:
        def _sub(m: re.Match[str], _repl: str = repl) -> str:
            if m.groups():
                # keep the context words, replace only the captured secret
                s, e = m.span(1)
                ms, _ = m.span(0)
                whole = m.group(0)
                return whole[: s - ms] + _repl + whole[e - ms:]
            return _repl
        new = pat.sub(_sub, out)
        if new != out:
            found.append(kind)
            out = new
    return out, sorted(set(found))


def redact_obj(obj: Any) -> Any:
    """Recursively redact strings inside dicts/lists (for bundles and audit records)."""
    if isinstance(obj, str):
        return redact(obj)[0]
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in {"full_name", "phone", "contact_phone", "date_of_birth"}:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_obj(v)
        return out
    return obj


def mask_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(p[0] + "*" * max(1, len(p) - 1) for p in name.split())
