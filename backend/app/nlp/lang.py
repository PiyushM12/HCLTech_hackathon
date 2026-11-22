"""Deterministic language and script detection (R1, R6).

Script detection is plain code: Unicode ranges are exact, so there is no reason to ask a
model. For Roman-script text we separate English, Hinglish and (best effort) Romanised Tamil
or Kannada with small marker-word lists."""
from __future__ import annotations

import re
from dataclasses import dataclass

RANGES = {
    "devanagari": (0x0900, 0x097F),
    "kannada": (0x0C80, 0x0CFF),
    "tamil": (0x0B80, 0x0BFF),
}
SCRIPT_TO_LANG = {"devanagari": "hi", "kannada": "kn", "tamil": "ta"}

HINGLISH = set("""
hai hain kya ka ki ke ko mera meri mere mujhe humein hum aap aapka aapki kaun kaunsi kaunse
liye lagenge lagega lagegi milegi milega milenge milta milti nahi nahin kaise kab kitna kitni
kitne paise maang raha rahi baat karna karni chahiye hoon hun bhi aur yojana yojna kisan beti
maa mummy pitaji papa saal umar umra ghar gaon kheti batao bataiye sakti sakta sakte wala wali
tak abhi ji sarkari apna apni iske uske aaya aayi baar teesri dusri kisi bade adhikari kahan
kya karu karoon karun sahi galat bhai behen padhai padhti padhta mahina mahine lakh hazaar
kagaz kaagaz dastavez bharna bhar do diya diye gaya gayi tha thi agar toh lekin par wapas
shikayat paisa rishwat ghoos milna dena lena jaana jana aana ana pata naam bolo boliye
""".split())
TANGLISH = set("""
enna enaku enakku amma appa venum vendum irukku iruku eppadi epdi kidaikuma kidaikum panna
pannanum sollunga naan unga ungal vayasu thittam illai illa romba yaaru enga ponnu vanakkam
kudumbam varumanam ennoda en ennudaya evlo evvalavu thevai kodukka sir madam aagum mudiyuma
""".split())
KANGLISH = set("""
nanna nange nanage beku bekagide illa yenu enu hege sigutta sigabahude thayi thaayi vayassu
yojane maadi madbeku madi ide alli yaava hesaru raitha raita namaskara swalpa yaake hogi
banni kodi kelsa mane
""".split())
ENGLISH = set("""
the is are was were my our your i you we can could will would what which when where how who
for of to in on and or with get give need do does have has please this that it she he they
scheme schemes eligible apply income mother father documents date last open still book slot
""".split())


@dataclass
class LangResult:
    language: str          # hi | en | kn | ta | hinglish
    script: str            # devanagari | kannada | tamil | latin | mixed
    romanized: bool = False  # True for Tanglish / Kanglish
    ambiguous: bool = False


def script_counts(text: str) -> dict[str, int]:
    counts = {"devanagari": 0, "kannada": 0, "tamil": 0, "latin": 0}
    for ch in text:
        cp = ord(ch)
        if ("a" <= ch.lower() <= "z"):
            counts["latin"] += 1
            continue
        for name, (lo, hi) in RANGES.items():
            if lo <= cp <= hi:
                counts[name] += 1
                break
    return counts


def detect(text: str) -> LangResult:
    counts = script_counts(text)
    indic = {k: v for k, v in counts.items() if k != "latin"}
    top_indic = max(indic, key=indic.get)
    total_letters = sum(counts.values()) or 1
    if indic[top_indic] > 0:
        share = indic[top_indic] / total_letters
        script = top_indic if share >= 0.3 else "mixed"
        return LangResult(SCRIPT_TO_LANG[top_indic], script)
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens:
        return LangResult("en", "latin")
    h = sum(t in HINGLISH for t in tokens)
    ta = sum(t in TANGLISH for t in tokens)
    kn = sum(t in KANGLISH for t in tokens)
    en = sum(t in ENGLISH for t in tokens)
    best = max(("hinglish", h), ("ta", ta), ("kn", kn), key=lambda x: x[1])
    if best[1] >= 2 or (best[1] >= 1 and best[1] >= en):
        if best[0] == "hinglish":
            return LangResult("hinglish", "latin")
        ambiguous = ta > 0 and kn > 0 and ta == kn
        return LangResult(best[0], "latin", romanized=True, ambiguous=ambiguous)
    return LangResult("en", "latin")


def script_share(text: str, lang: str) -> float:
    """Share of letters in the script expected for `lang` (used by the critic)."""
    counts = script_counts(text)
    total = sum(counts.values()) or 1
    key = {"hi": "devanagari", "kn": "kannada", "ta": "tamil"}.get(lang, "latin")
    return counts[key] / total


def reply_language(detected: LangResult, requested: str | None) -> str:
    """The language we answer in: an explicit `language` field wins (R6)."""
    if requested:
        return requested
    return detected.language
