"""Generate the synthetic citizen kit (citizens, applications, appointments) in the Annex C schema.

Two sources, on purpose:
1. LLM-generated profiles for variety (names, districts, occupations, incomes). They come from
   `data/synthetic/llm_raw/*.json` (raw model output, kept verbatim) or, with `--llm ollama`,
   from a fresh call to the local model using data/prompts/citizen_generation_prompt_v1.md.
   Every profile is validated with Pydantic; invalid ones are reported and dropped.
2. Boundary edge cases written by code, because they must sit *exactly* on a rule limit relative
   to the as-of date (an LLM cannot be trusted to hit "one day short of 60" on 2026-11-21).

Usage:
    python scripts/generate_citizens.py                 # from the saved raw LLM output
    python scripts/generate_citizens.py --llm ollama --n 25
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "synthetic"
RAW = OUT / "llm_raw"
PROMPT = ROOT / "data" / "prompts" / "citizen_generation_prompt_v1.md"
AS_OF = date(2026, 11, 21)

Occupation = Literal["farmer", "student", "daily_wage", "construction_worker", "street_vendor", "homemaker",
                     "retired", "unemployed", "salaried", "self_employed"]


class LLMCitizen(BaseModel):
    full_name: str = Field(min_length=3, max_length=60)
    gender: Literal["female", "male", "other"]
    date_of_birth: date
    district: Literal["Nayagaon", "Sundarpur", "Kaverinadu", "Thenpuram"]
    residence_type: Literal["rural", "urban"]
    annual_household_income: int = Field(ge=0, le=5_000_000)
    occupation: Occupation
    category: Literal["general", "obc", "sc", "st"]
    is_disabled: Literal["Y", "N"]
    disability_percent: int = Field(ge=0, le=100)
    land_holding_acres: float = Field(ge=0, le=100)
    preferred_language: Literal["hi", "en", "kn", "ta"]
    consent_given: Literal["Y", "N"]

    @field_validator("date_of_birth")
    @classmethod
    def _age(cls, v: date) -> date:
        age = AS_OF.year - v.year - ((AS_OF.month, AS_OF.day) < (v.month, v.day))
        if not 0 <= age <= 110:
            raise ValueError(f"implausible age {age}")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> "LLMCitizen":
        if self.is_disabled == "N" and self.disability_percent != 0:
            raise ValueError("disability_percent must be 0 when is_disabled is N")
        if self.is_disabled == "Y" and self.disability_percent == 0:
            raise ValueError("is_disabled Y needs a disability_percent")
        return self


# ------------------------------------------------------------------ deterministic edge cases
EDGE_CASES: list[dict] = [
    # id, why it exists
    dict(citizen_id="C1001", note="income exactly at the pension limit (150000)", full_name="Savitri Bai", gender="female",
         date_of_birth="1959-05-10", district="Nayagaon", residence_type="rural", annual_household_income=150000,
         occupation="retired", category="obc", is_disabled="N", disability_percent=0, land_holding_acres=0,
         preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1002", note="income one rupee over the pension limit (150001)", full_name="Shanti Devi",
         gender="female", date_of_birth="1958-02-02", district="Sundarpur", residence_type="urban",
         annual_household_income=150001, occupation="homemaker", category="general", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1003", note="age exactly 60 on 2026-11-21 (pension minimum)", full_name="Hariprasad Tiwari",
         gender="male", date_of_birth="1966-11-21", district="Nayagaon", residence_type="rural",
         annual_household_income=100000, occupation="retired", category="general", is_disabled="N",
         disability_percent=0, land_holding_acres=1.0, preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1004", note="one day short of 60 on 2026-11-21", full_name="Ramkali Devi", gender="female",
         date_of_birth="1966-11-22", district="Nayagaon", residence_type="rural", annual_household_income=100000,
         occupation="homemaker", category="obc", is_disabled="N", disability_percent=0, land_holding_acres=0,
         preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1005", note="land holding exactly at the Kisan Samriddhi cap (5 acres)", full_name="Mahesh Patel",
         gender="male", date_of_birth="1981-08-19", district="Nayagaon", residence_type="rural",
         annual_household_income=200000, occupation="farmer", category="obc", is_disabled="N", disability_percent=0,
         land_holding_acres=5.0, preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1006", note="eligible for several overlapping schemes (pension + Kisan + housing)",
         full_name="Gopal Singh", gender="male", date_of_birth="1963-06-01", district="Nayagaon", residence_type="rural",
         annual_household_income=90000, occupation="farmer", category="sc", is_disabled="N", disability_percent=0,
         land_holding_acres=2.0, preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1007", note="already applied (pension submitted 2026-10-20)", full_name="Usha Rani",
         gender="female", date_of_birth="1956-04-04", district="Sundarpur", residence_type="urban",
         annual_household_income=80000, occupation="retired", category="general", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="en", consent_given="Y"),
    dict(citizen_id="C1008", note="application rejected (age record mismatch)", full_name="Baldev Raj", gender="male",
         date_of_birth="1960-01-15", district="Nayagaon", residence_type="rural", annual_household_income=110000,
         occupation="farmer", category="obc", is_disabled="N", disability_percent=0, land_holding_acres=1.5,
         preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1009", note="application pending beyond the 45-day target (submitted 2026-08-14)",
         full_name="Jamuna Prasad", gender="male", date_of_birth="1954-07-07", district="Nayagaon",
         residence_type="rural", annual_household_income=70000, occupation="retired", category="sc", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="hi", consent_given="Y"),
    dict(citizen_id="C1010", note="profile with missing attributes (income, occupation, land)", full_name="Kiran Kumar",
         gender="male", date_of_birth="1975-09-09", district="Kaverinadu", residence_type="rural",
         annual_household_income="", occupation="", category="", is_disabled="N", disability_percent=0,
         land_holding_acres="", preferred_language="kn", consent_given="Y"),
    dict(citizen_id="C1011", note="Medhavi scholarship: last date is today (2026-11-21)", full_name="Aditya Rao",
         gender="male", date_of_birth="2008-03-03", district="Kaverinadu", residence_type="urban",
         annual_household_income=250000, occupation="student", category="general", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="kn", consent_given="Y"),
    dict(citizen_id="C1012", note="Suraksha Bima: last date was yesterday (2026-11-20)", full_name="Velu Murugan",
         gender="male", date_of_birth="1991-02-14", district="Thenpuram", residence_type="rural",
         annual_household_income=120000, occupation="daily_wage", category="obc", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="ta", consent_given="Y"),
    dict(citizen_id="C1013", note="income exactly at the Kanya Vidya limit (250000)", full_name="Priya Natarajan",
         gender="female", date_of_birth="2009-06-30", district="Thenpuram", residence_type="urban",
         annual_household_income=250000, occupation="student", category="obc", is_disabled="N",
         disability_percent=0, land_holding_acres=0, preferred_language="ta", consent_given="Y"),
]

APPLICATIONS = [
    ("APP-1001", "C1007", "SCH-PEN-01", "submitted", "2026-10-20", ""),
    ("APP-1002", "C1008", "SCH-PEN-01", "rejected", "2026-09-05", "Age record mismatch between ration card and age certificate"),
    ("APP-1003", "C1009", "SCH-PEN-01", "submitted", "2026-08-14", ""),
    ("APP-1004", "C1014", "SCH-PEN-01", "approved", "2026-06-12", "Approved; pension from July 2026"),
    ("APP-1005", "C1023", "SCH-FRM-01", "submitted", "2026-11-01", ""),
    ("APP-1006", "C1030", "SCH-SCH-01", "submitted", "2026-10-15", ""),
    ("APP-1007", "C1006", "SCH-FRM-01", "approved", "2026-07-20", "First instalment paid August 2026"),
]
APPOINTMENTS = [
    ("APT-S001", "C1007", "JSK-SDP-01", "2026-11-26T11:00:00+05:30", "booked", "2026-11-19T10:15:00+05:30"),
    ("APT-S002", "C1023", "JSK-KVN-01", "2026-11-10T10:30:00+05:30", "booked", "2026-11-05T09:00:00+05:30"),
]

COLUMNS = ["citizen_id", "full_name", "phone", "date_of_birth", "gender", "district", "residence_type",
           "annual_household_income", "occupation", "category", "is_disabled", "disability_percent",
           "land_holding_acres", "preferred_language", "consent_given", "national_id_last4", "edge_case_note"]


def call_ollama(n: int, focus: str) -> list[dict]:
    from app.llm import LLMStats, llm

    class Batch(BaseModel):
        citizens: list[dict]

    prompt = PROMPT.read_text(encoding="utf-8").split("---", 1)[1].replace("{n}", str(n)).replace("{focus}", focus)
    stats = LLMStats()
    res = llm.structured("You output strict JSON only.", prompt, Batch, stats, retries=1)
    if res is None:
        raise SystemExit(f"LLM call failed: {stats.errors}")
    return res.citizens


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["saved", "ollama"], default="saved")
    ap.add_argument("--n", type=int, default=25)
    args = ap.parse_args()
    rnd = random.Random(42)
    raw: list[dict] = []
    if args.llm == "ollama":
        foci = ["Nayagaon and Sundarpur, Hindi speakers", "Kaverinadu, Kannada speakers", "Thenpuram, Tamil speakers",
                "elderly and disabled citizens across all districts", "students and daily-wage workers"]
        for i in range(0, args.n, 5):
            batch = call_ollama(5, foci[(i // 5) % len(foci)])
            (RAW / f"citizens_ollama_{i // 5 + 1:02d}.json").write_text(json.dumps({"citizens": batch}, ensure_ascii=False, indent=1), encoding="utf-8")
            raw += batch
    else:
        for f in sorted(RAW.glob("*.json")):
            raw += json.loads(f.read_text(encoding="utf-8"))["citizens"]
    rows, rejected = [], []
    for c in EDGE_CASES:
        rows.append(dict(c))
    next_id = 1014
    for item in raw:
        try:
            v = LLMCitizen.model_validate(item)
        except ValidationError as e:
            rejected.append({"item": item, "errors": [er["msg"] for er in e.errors()]})
            continue
        d = v.model_dump()
        d["date_of_birth"] = v.date_of_birth.isoformat()
        d["citizen_id"] = f"C{next_id}"
        d["note"] = ""
        next_id += 1
        rows.append(d)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "citizens.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            num = r["citizen_id"][1:]
            w.writerow({**{k: r.get(k, "") for k in COLUMNS}, "phone": f"000-000-{num}",
                        "national_id_last4": f"{rnd.randint(0, 9999):04d}", "edge_case_note": r.get("note", "")})
    with (OUT / "applications.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["application_id", "citizen_id", "scheme_id", "status", "status_updated_on", "remarks"])
        w.writerows(APPLICATIONS)
    with (OUT / "appointments.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["appointment_id", "citizen_id", "centre_id", "slot_start", "status", "created_at"])
        w.writerows(APPOINTMENTS)
    (OUT / "generation_log.json").write_text(json.dumps(
        {"source": args.llm, "raw_profiles": len(raw), "accepted": len(rows) - len(EDGE_CASES),
         "edge_cases": len(EDGE_CASES), "rejected": rejected}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} citizens ({len(EDGE_CASES)} edge cases, {len(rows) - len(EDGE_CASES)} from LLM), "
          f"{len(rejected)} LLM profiles rejected")


if __name__ == "__main__":
    main()
