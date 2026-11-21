"""Rule engine: boundaries, OR groups, amendments by date, conflicts (R4, R9, Annex A.3)."""
from app import tools

AS_OF = "2026-11-21"


def verdict(conn, attrs, sid, as_of=AS_OF):
    return tools.check_eligibility(conn, attrs, [sid], as_of)[0]


def test_income_exactly_at_limit_passes(conn):
    assert verdict(conn, {"age": 67, "annual_household_income": 150000}, "SCH-PEN-01").verdict == "appears_eligible"


def test_income_one_rupee_over_fails(conn):
    v = verdict(conn, {"age": 67, "annual_household_income": 150001}, "SCH-PEN-01")
    assert v.verdict == "not_eligible" and v.failed == ["PEN-R2B"]


def test_age_exactly_minimum_and_one_day_short(conn):
    assert tools.age_on("1966-11-21", AS_OF) == 60
    assert tools.age_on("1966-11-22", AS_OF) == 59
    assert verdict(conn, {"age": 59, "annual_household_income": 1}, "SCH-PEN-01").verdict == "not_eligible"


def test_amendment_replaces_clause_from_its_date(conn):
    # before 2026-07-01 the old limit (120000) applies; after, the amended one (150000)
    assert verdict(conn, {"age": 70, "annual_household_income": 130000}, "SCH-PEN-01", "2026-06-15").verdict == "not_eligible"
    assert verdict(conn, {"age": 70, "annual_household_income": 130000}, "SCH-PEN-01").verdict == "appears_eligible"


def test_land_exactly_at_cap(conn):
    v = verdict(conn, {"occupation": "farmer", "land_holding_acres": 5, "annual_household_income": 100000}, "SCH-FRM-01")
    assert v.verdict == "appears_eligible"
    v = verdict(conn, {"occupation": "farmer", "land_holding_acres": 5.01, "annual_household_income": 100000}, "SCH-FRM-01")
    assert v.verdict == "not_eligible"


def test_missing_attribute_needs_more_information(conn):
    v = verdict(conn, {"age": 67}, "SCH-PEN-01")
    assert v.verdict == "need_more_information" and v.unknown == ["annual_household_income"]


def test_failed_rule_beats_unknown(conn):
    v = verdict(conn, {"age": 40}, "SCH-PEN-01")
    assert v.verdict == "not_eligible"


def test_or_group_and_unreflected_amendment(conn):
    base = {"residence_type": "rural", "annual_household_income": 150000, "land_holding_acres": 1}
    # CIR-2026-016 raised the income limit but no rule row reflects it -> provisional
    assert verdict(conn, {**base, "category": "sc"}, "SCH-HSG-01").verdict == "verify_with_officer"
    # before that circular took effect, the OR group decides
    assert verdict(conn, {**base, "category": "sc"}, "SCH-HSG-01", "2026-11-01").verdict == "appears_eligible"
    v = verdict(conn, {**base, "category": "general", "is_disabled": "N"}, "SCH-HSG-01", "2026-11-01")
    assert v.verdict == "not_eligible" and {"GAS-R4A", "GAS-R4B", "GAS-R4C"} <= set(v.failed)


def test_loading_a_rule_row_resolves_the_conflict(conn):
    from app import loader
    n, errs = loader.load_rows(conn, "eligibility_rules", [{
        "rule_id": "GAS-R2B", "scheme_id": "SCH-HSG-01", "attribute": "annual_household_income", "operator": "<=",
        "value": "200000", "rule_group": "", "effective_from": "2026-11-15", "valid_until": "",
        "source_id": "CIR-2026-016", "source_section": "2 Revised income limit"}])
    conn.execute("UPDATE eligibility_rules SET valid_until='2026-11-14' WHERE rule_id='GAS-R2'")
    conn.commit()
    try:
        v = verdict(conn, {"residence_type": "rural", "annual_household_income": 190000, "land_holding_acres": 1,
                           "category": "st"}, "SCH-HSG-01")
        assert n == 1 and not errs and v.verdict == "appears_eligible"
    finally:
        conn.execute("DELETE FROM eligibility_rules WHERE rule_id='GAS-R2B'")
        conn.execute("UPDATE eligibility_rules SET valid_until='' WHERE rule_id='GAS-R2'")
        conn.commit()


def test_future_income_change_is_reported_not_applied(conn):
    v = verdict(conn, {"occupation": "student", "age": 19, "annual_household_income": 350000}, "SCH-SCH-02")
    assert v.verdict == "not_eligible"
    assert any(u.get("rule_id") == "MCP-R3B" for u in v.upcoming_changes)


def test_scheme_status_extension_closure_and_deadlines(conn):
    def st(sid):
        return tools.get_scheme(conn, sid, AS_OF)["effective"]
    assert st("SCH-SCH-01")["apply_until"] == "2026-12-15"          # extended by CIR-2026-011
    assert st("SCH-FRM-02")["status"] == "closed"                    # closure circular
    assert st("SCH-INS-01")["status"] == "closed"                    # last date was yesterday
    assert st("SCH-SCH-02")["days_left"] == 0                        # last date is today
    assert st("SCH-HSG-02")["status"] == "upcoming"
