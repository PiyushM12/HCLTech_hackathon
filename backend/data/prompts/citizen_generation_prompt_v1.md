# Citizen profile generation prompt (v1) — verbatim

Model: Claude (the AI coding assistant used to build this project), temperature default, 1 call for 25 profiles.
The same prompt is used by `scripts/generate_citizens.py --llm ollama` (qwen2.5:7b-instruct, temperature 0.7,
batches of 5, JSON mode, Pydantic validation, one retry with the validation error).

---

You generate SYNTHETIC citizen profiles for a fictional Indian state called "Mitrapur Pradesh".
No real people. Names must be common but generic; never use celebrities or public figures.

Districts and their main languages:
- Nayagaon (Hindi, mostly rural), Sundarpur (Hindi and English, mostly urban),
- Kaverinadu (Kannada), Thenpuram (Tamil).

Return ONLY a JSON object: {"citizens": [ ... ]} with exactly {n} items. Each item has these keys:
- full_name: string, a plausible name for the district's language community
- gender: "female" | "male" | "other"
- date_of_birth: "YYYY-MM-DD" (ages 14 to 85 on 2026-11-21)
- district: one of Nayagaon, Sundarpur, Kaverinadu, Thenpuram
- residence_type: "rural" | "urban"
- annual_household_income: integer INR per year, 0 to 600000
- occupation: farmer | student | daily_wage | construction_worker | street_vendor | homemaker | retired |
  unemployed | salaried | self_employed
- category: general | obc | sc | st
- is_disabled: "Y" | "N"
- disability_percent: integer 0-100 (0 when is_disabled is "N")
- land_holding_acres: number >= 0 (0 for most urban and landless households)
- preferred_language: hi | en | kn | ta (match the district: Kaverinadu mostly kn, Thenpuram mostly ta)
- consent_given: "Y" | "N"

Constraints:
- Mix rural and urban; mix incomes (many below ₹2,00,000, some above ₹3,00,000).
- Include farmers with 0.5–6 acres, students aged 14–25 (both genders), people aged 60+, at least two people
  with a disability (one below 40%, one above), daily-wage and construction workers aged 18–59.
- Do NOT include phone numbers, ID numbers, addresses or bank details.
- Keep values internally consistent (a 15-year-old is a student, not retired; is_disabled N means 0%).

Batch focus for this call: {focus}
