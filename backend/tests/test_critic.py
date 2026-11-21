"""The critic must catch a wrong number, a missing caveat, the wrong language and a promise (R7)."""
from app.agents import critic

EVIDENCE = ['{"rules": [{"rule_id": "PEN-R2B", "value": "150000"}, {"rule_id": "PEN-R1", "value": "60"}]}',
            "Benefit ₹1,500 per month. GL-PEN-01 3 Eligibility"]


def review(text, lang="en", has_verdict=True, cites=(("GL-PEN-01", "3"),), revisions=0, hist=None):
    return critic.review(draft={"text": text, "cites": list(cites), "kind": "eligibility", "used_hits": []}, lang=lang,
                         evidence_authoritative=EVIDENCE + ["age 67"], evidence_historical=hist or [], retrieved=[],
                         answer_kind="eligibility", has_verdict=has_verdict, threshold=0.8, revisions=revisions,
                         max_revisions=1)


GOOD = "You told me: age 67. Appears eligible to apply; the income limit is ₹1,50,000. The department makes the final decision."


def test_good_draft_passes():
    assert review(GOOD).decision == "answer"


def test_wrong_number_is_caught():
    out = review(GOOD.replace("1,50,000", "1,80,000"))
    assert out.decision == "revise" and out.groundedness < 0.8


def test_outdated_number_from_grievance_is_caught():
    out = review(GOOD.replace("1,50,000", "1,20,000"), hist=["the limit is ₹1,20,000"])
    assert out.decision == "revise" and any("historical" in i for i in out.issues)


def test_missing_caveat_is_caught():
    out = review("You told me: age 67. Appears eligible to apply; the income limit is ₹1,50,000.")
    assert out.coverage == "partial" and out.decision == "revise"


def test_wrong_language_is_caught():
    out = review(GOOD, lang="hi")
    assert out.language_fidelity == "poor" and out.decision == "revise"


def test_promise_is_caught():
    out = review(GOOD + " You will definitely get the pension.")
    assert out.promise_risk == "high" and out.decision == "revise"


def test_refer_after_one_revision():
    assert review(GOOD.replace("1,50,000", "1,80,000"), revisions=1).decision == "refer"


def test_pii_is_caught():
    out = review(GOOD + " Call 9876543210.")
    assert out.pii_risk == "high"
