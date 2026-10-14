"""python -m ordner.rules.selfcheck  (asserts on reference cases; no network; the Noa case uses a temporary DB)"""
import re
import tempfile
from datetime import date
from pathlib import Path

from ordner.case import demo_seed
from ordner.case.store import Store
from ordner.core.schema import Deadline, DeadlineRule, Document, Fact, ProcedureCard, Subject
from ordner.procedures.catalog import _condition as catalog_syntax
from ordner.procedures.catalog import get as get_card

from . import DEADLINE_RULE_IDS, applicable, completeness, compute_deadline, consolidate, easter, holidays, reminders, to_ics

VD = Subject("s_vd", "person", "Léa Test", canton="VD", roles=["student"], attrs={"birth_year": 2006})


def due(rule_id, params=None, subject=VD, **context):
    return compute_deadline(DeadlineRule(rule_id, params or {}), subject, context)


def check_calendar():
    assert [easter(y).isoformat() for y in (2025, 2026, 2027)] == ["2025-04-20", "2026-04-05", "2027-03-28"]
    vd, ge, ti = holidays(2026, "VD"), holidays(2026, "GE"), holidays(2026, "TI")
    assert vd[date(2026, 9, 21)] == "Lundi du Jeûne fédéral"
    assert any(n == "Jeûne genevois" and d.isoformat() == "2026-09-10" for d, n in ge.items())
    assert "Vendredi saint" not in ti.values() and "Fête-Dieu" in ti.values()
    assert list(holidays(2026).values()) == ["Fête nationale"]


def check_debt_collection():
    # 10 days LP ending in the 15-31 July holidays → 3rd working day after 31.07 (1.8 = Saturday + national day)
    r = due("debt_collection", notified_on="2026-07-10")
    assert r["due"] == "2026-08-05" and {"lp_56", "lp_63", "lp_74"} <= set(r["computed_from"]["legal_basis"]), r
    # holidays do not suspend the deadline: an end after 31.07 stays where it is
    assert due("debt_collection", notified_on="2026-07-24")["due"] == "2026-08-03"
    # end in the Christmas holidays; the 3rd working day depends on the canton (6 January is a holiday in TI)
    assert due("debt_collection", notified_on="2026-12-10")["due"] == "2027-01-06"
    assert due("debt_collection", subject=Subject("s_ti", "person", "T", canton="TI"), notified_on="2026-12-10")["due"] == "2027-01-07"
    # end on Sunday 12.07, CPC 142 al. 3 moves it to Monday 13.07 (féries start on 15.07, so no LP 63 extension)
    assert due("debt_collection", notified_on="2026-07-02")["due"] == "2026-07-13"
    # end on Sunday 29.03.2026, inside the Easter holidays (29.03-12.04) → 3rd working day after 12.04 (VD): 15.04
    assert due("debt_collection", notified_on="2026-03-19")["due"] == "2026-04-15"


def check_days_after_notification():
    # 30 days (tax assessment) ending on Sunday 01.11.2026 → Monday 02.11
    r = due("days_after_notification", {"days": 30}, notified_on="2026-10-02")
    assert r["due"] == "2026-11-02" and "dimanche" in " ".join(r["computed_from"]["steps"]), r
    # ending on the Lundi du Jeûne: holiday in VD, working day in ZH
    assert due("days_after_notification", {"days": 10}, notified_on="2026-09-11")["due"] == "2026-09-22"
    zh = Subject("s_zh", "person", "Z", canton="ZH")
    assert due("days_after_notification", {"days": 10}, subject=zh, notified_on="2026-09-11")["due"] == "2026-09-21"
    # business days: 5 working days after Wednesday 30.07.2025, skipping Friday 1 August and the weekend → 07.08
    assert due("days_after_notification", {"days": 5, "count": "business"}, notified_on="2025-07-30")["due"] == "2025-08-07"
    # unknown canton → computed with federal holidays only and flagged as the earliest (safe) date
    r = due("days_after_notification", {"days": 10}, subject=Subject("s_x", "person", "X"), notified_on="2026-09-11")
    assert r["due"] == "2026-09-21" and "prudente" in r["computed_from"]["warnings"][0]


def check_fixed_dates():
    lamal = due("reception_by", {"month": 11, "day": 30, "sources": [0]}, period="2026")
    assert lamal["due"] == "2026-11-30" and lamal["send_by"] == "2026-11-23", lamal
    assert "RÉCEPTION" in lamal["computed_from"]["warnings"][-1] and lamal["computed_from"]["card_sources"] == [0]
    ofsp = due("reception_by", {"month": 11, "day": 30, "send_by": {"month": 11, "day": 15}}, period="2026")
    assert ofsp["send_by"] == "2026-11-13"  # 15.11.2026 is a Sunday → post on Friday
    table = {"table": {"VD": {"month": 3, "day": 15, "year_offset": 1, "sources": [1], "extensions": [
        {"until": "06-30", "fee_chf": 0, "how": "tolérance sans demande"},
        {"until": "09-30", "fee_chf": 0, "how": "e-Délai", "request_by": "06-30"}]},
        "ZH": {"month": 3, "day": 31, "year_offset": 1}}}
    vd = due("cantonal_table", table, period="2025")
    assert vd["due"] == "2026-03-15" and "dimanche" in vd["computed_from"]["warnings"][0], vd
    assert vd["extensions"][1] == {"until": "2026-09-30", "fee_chf": 0, "how": "e-Délai", "request_by": "2026-06-30"}
    assert vd["computed_from"]["card_sources"] == [1]
    assert due("cantonal_table", table, period="2025", extension=1)["due"] == "2026-09-30"
    assert due("cantonal_table", table, period="2025", canton="ZH")["due"] == "2026-03-31"
    assert due("year_end", period="2026")["due"] == "2026-12-31"
    assert due("fixed_date", {"month": 3, "day": 31, "year_offset": 1}, period="2025")["due"] == "2026-03-31"


def check_missing_info():
    for r, key in [(due("debt_collection"), "notified_on"),
                   (due("fixed_date", {"month": 3, "day": 15}), "period"),
                   (due("cantonal_table", {"table": {"VD": {"month": 3, "day": 15}}}, subject=Subject("s", "person", "N"), period="2025"), "subject.canton"),
                   (due("cantonal_table", {"table": {"VD": {"month": 3, "day": 15}}}, period="2025", canton="TI"), "table.TI"),
                   (due("cantonal_table", {"table": {"VD": {"month": 3, "day": 15}}}, period="2025", extension=4), "extension")]:
        assert r["status"] == "missing_info" and r["missing"] == [key] and r["why"], r
    try:
        due("no_such_rule")
        raise AssertionError("unknown rule accepted")
    except ValueError:
        pass


def card(applicability, jurisdiction="CH", **kw):
    return ProcedureCard(id="pension.avs.non_active", name={"fr": "AVS"}, domain="pension", nature="obligation",
                         jurisdiction=jurisdiction, applicability=applicability, qualification="draft", **kw)


def check_applicability():
    # AHV non-active: contributions from 1 January after the 20th birthday (LAVS art. 3 al. 1bis) ⇔ age at 31.12 ≥ 21
    avs = card({"all": [{"not": {"role": "salaried"}}, {"attr": "age_at_year_end", "gte": 21}]})
    assert catalog_syntax(avs.applicability, "applicability") == []  # same syntax as W2a's validator
    r = applicable(avs, VD, [], on="2026-10-14")
    assert r["status"] == "not_applicable" and r["missing"] == [] and "âge au 31.12.2026 (2026 − 2006) = 20" in " ".join(r["why"]), r
    assert applicable(avs, VD, [], on="2027-01-01")["status"] == "applicable"
    born_2005 = Subject("s5", "person", "B", canton="VD", roles=["student"], attrs={"birth_year": 2005})
    assert applicable(avs, born_2005, [], on="2026-10-14")["status"] == "applicable"
    no_year = Subject("s6", "person", "C", canton="VD", roles=["student"])
    r = applicable(avs, no_year, [], on="2026-10-14")
    assert r["status"] == "missing_info" and r["missing"] == ["subject.birth_year"], r
    # age_at_year_end follows the evaluated period, not the evaluation date: 18 in 2026 → not bound for 2025, bound for 2026
    tax18 = card({"attr": "age_at_year_end", "gte": 18})
    turns_18 = Subject("s18", "person", "G", attrs={"birth_year": 2008})
    assert applicable(tax18, turns_18, [], on="2026-03-01", period="2025")["status"] == "not_applicable"
    assert applicable(tax18, turns_18, [], on="2027-03-01", period="2026")["status"] == "applicable"
    assert applicable(tax18, turns_18, [], on="2026-03-01")["status"] == "applicable"  # no period → year of `on`
    # salaried short-circuits to not_applicable even with the birth year unknown
    worker = Subject("s7", "person", "D", roles=["salaried"])
    assert applicable(avs, worker, [])["status"] == "not_applicable"
    # empty roles = unknown, not "no role"
    assert applicable(avs, Subject("s8", "person", "E", attrs={"birth_year": 2000}), [])["missing"] == ["subject.roles"]
    # exact age needs the birth date when the year alone is ambiguous
    adult = card({"attr": "age", "gte": 18})
    r = applicable(adult, Subject("s9", "person", "F", roles=["x"], attrs={"birth_year": 2008}), [], on="2026-06-01")
    assert r["status"] == "missing_info" and r["missing"] == ["subject.birth_date"], r
    assert applicable(adult, Subject("s9", "person", "F", attrs={"birth_date": "2008-05-31"}), [], on="2026-06-01")["status"] == "applicable"
    assert applicable(adult, Subject("s9", "person", "F", attrs={"birth_year": 2000}), [], on="2026-06-01")["status"] == "applicable"
    # jurisdiction: a VD card does not apply to a ZH subject, and needs the canton
    vd_card = card({"role": "student"}, jurisdiction="VD")
    assert applicable(vd_card, Subject("z", "person", "Z", canton="ZH", roles=["student"]), [])["status"] == "not_applicable"
    assert applicable(vd_card, Subject("z", "person", "Z", roles=["student"]), [])["missing"] == ["subject.canton"]
    # facts: confirmed decides, proposed only asks for confirmation (or counts in preview mode), others' facts ignored
    claim = card({"fact": "tax.assessment.notified_on", "exists": True})
    proposed = Fact("f1", "s_vd", "tax.assessment.notified_on", "2026-10-02", status="proposed")
    r = applicable(claim, VD, [proposed])
    assert r["status"] == "missing_info" and r["missing"] == ["tax.assessment.notified_on"] and "à confirmer" in r["why"][0], r
    assert applicable(claim, VD, [proposed], accept_proposed=True)["status"] == "applicable"
    confirmed = Fact("f2", "s_vd", "tax.assessment.notified_on", "2026-10-02", status="confirmed")
    assert applicable(claim, VD, [proposed, confirmed])["status"] == "applicable"
    assert applicable(claim, VD, [Fact("f3", "other", "tax.assessment.notified_on", "x", status="confirmed")])["status"] == "not_applicable"
    income = card({"fact": "income.net", "lte": 46800})
    assert applicable(income, VD, [])["missing"] == ["income.net"]
    assert applicable(income, VD, [Fact("f4", "s_vd", "income.net", 30000, status="confirmed")])["status"] == "applicable"
    assert applicable(income, VD, [Fact("f5", "s_vd", "income.net", 50000, status="rejected")])["status"] == "missing_info"
    # any: one true branch decides even if the other is unknown
    either = card({"any": [{"attr": "canton", "in": ["VD", "GE"]}, {"fact": "x.y", "eq": 1}]})
    assert applicable(either, VD, [])["status"] == "applicable"
    # card validity: an expired card yields missing_info, never a silent yes
    old = card({}, valid_to="2025-12-31")
    assert applicable(old, VD, [], on="2026-10-14")["missing"] == ["card.validity"]


def check_reminders_and_ics():
    assert reminders("2026-11-30") == ["2026-10-31", "2026-11-23", "2026-11-29"]
    assert reminders("2026-11-30", today="2026-11-24") == ["2026-11-29"]
    assert reminders("2026-08-05", policy="short") == ["2026-08-02", "2026-08-04"]
    lp = due("debt_collection", notified_on="2026-07-10", label="Opposition au commandement de payer, poursuite n° 123; office VD")
    dls = [Deadline("dl_1", "case_1", lp["due"], "debt_collection", lp["computed_from"], reminders(lp["due"], "short")),
           Deadline("dl_2", "case_2", "2026-11-30", "reception_by", {})]
    ics = to_ics(dls, VD)
    assert ics.endswith("\r\n") and "\n" not in ics.replace("\r\n", "")
    lines = ics.split("\r\n")[:-1]
    assert all(len(line.encode()) <= 75 for line in lines)
    unfolded = re.sub(r"\r\n ", "", ics).split("\r\n")[:-1]
    stack = []
    for line in unfolded:
        if line.startswith("BEGIN:"):
            stack.append(line[6:])
        elif line.startswith("END:"):
            assert stack.pop() == line[4:]
    assert not stack and unfolded[0] == "BEGIN:VCALENDAR" and "VERSION:2.0" in unfolded and any(l.startswith("PRODID:") for l in unfolded)
    assert unfolded.count("BEGIN:VEVENT") == 2 and unfolded.count("BEGIN:VALARM") == 2 + 3
    assert "DTSTART;VALUE=DATE:20260805" in unfolded and "DTEND;VALUE=DATE:20260806" in unfolded
    assert "TRIGGER;VALUE=DATE-TIME:20260804T080000Z" in unfolded
    assert any(l.startswith("SUMMARY:Opposition au commandement de payer\\, poursuite n° 123\\; office VD") for l in unfolded)
    assert all(re.fullmatch(r"DTSTAMP:\d{8}T\d{6}Z", l) for l in unfolded if l.startswith("DTSTAMP"))


def check_card_params():
    """from_fact, cantonal, kinds, variants and chosen_date, on W2b's real cards where they exist."""
    moving = get_card("housing.moving.announce").deadline
    move = lambda status: [Fact("m1", "s_vd", "housing.moving.date", "2026-10-01", status=status)]
    # 1. from_fact: the deadline counts from the confirmed moving date; proposed or absent → missing_info
    r = compute_deadline(moving, VD, {"facts": move("confirmed")})
    assert r["due"] == "2026-10-09" and r["computed_from"]["inputs"]["from_fact"] == "housing.moving.date", r  # VD: 8 days
    assert compute_deadline(moving, VD, {"facts": move("proposed")})["missing"] == ["housing.moving.date"]
    assert compute_deadline(moving, VD, {})["missing"] == ["housing.moving.date"]
    # 2. cantonal: VD 8 days and its sources; ZH has no own rule → federal 14 days, flagged; no canton → missing
    assert compute_deadline(moving, VD, {"facts": move("confirmed")})["computed_from"]["card_sources"][:2] == [1, 2]
    zh = compute_deadline(moving, Subject("s_vd", "person", "Z", canton="ZH"), {"facts": move("confirmed")})
    assert zh["due"] == "2026-10-15" and "sans règle propre" in zh["computed_from"]["warnings"][0], zh
    assert compute_deadline(moving, Subject("s_vd", "person", "N"), {"facts": move("confirmed")})["missing"] == ["subject.canton"]
    #    with an event kind (FR: 14 days arrival, 30 days internal move, departure "sans délai")
    fr_rule = DeadlineRule("days_after_notification", {"days": 14, "from_fact": "housing.moving.date", "cantonal": {"FR": {
        "days": 14, "sources": [3], "kinds": {"internal": {"days": 30, "sources": [7]}, "departure": {"days": 0, "sources": [4]}}}}})
    fr = Subject("s_vd", "person", "F", canton="FR")
    assert compute_deadline(fr_rule, fr, {"facts": move("confirmed")})["missing"] == ["kind"]
    internal = compute_deadline(fr_rule, fr, {"facts": move("confirmed"), "kind": "internal"})
    assert internal["due"] == "2026-11-02" and internal["computed_from"]["kind"] == "internal", internal  # 31.10 = Saturday
    assert compute_deadline(fr_rule, fr, {"facts": move("confirmed"), "kind": "arrival"})["due"] == "2026-10-15"
    assert compute_deadline(fr_rule, fr, {"facts": move("confirmed"), "kind": "departure"})["due"] == "2026-10-01"
    #    a cantonal rule given only as text keeps the base computation and is surfaced
    objection = compute_deadline(get_card("tax.assessment.objection").deadline, VD, {"notified_on": "2026-10-02"})
    assert objection["due"] == "2026-11-02" and "LI-VD" in objection["computed_from"]["cantonal_rule"], objection
    # 3. variants: LAMal 30.11 reception (change, lower deductible) vs 31.12 (higher deductible)
    lamal = get_card("health_insurance.change_insurer_or_deductible").deadline
    both = compute_deadline(lamal, VD, {"period": "2026"})
    assert both["status"] == "variants" and both["missing"] == ["variant"], both
    assert [(v["cases"][0], v["due"]) for v in both["variants"]] == [("change_insurer", "2026-11-30"), ("higher_deductible", "2026-12-31")]
    low = compute_deadline(lamal, VD, {"period": "2026", "variant": "lower_deductible"})
    assert low["due"] == "2026-11-30" and low["send_by"] and low["computed_from"]["variant"] == "lower_deductible"
    assert compute_deadline(lamal, VD, {"period": "2026", "variant": "higher_deductible"})["due"] == "2026-12-31"
    assert compute_deadline(lamal, VD, {"period": "2026", "variant": "other"})["missing"] == ["variant"]
    # 4. chosen_date: ORP registration at the latest on the first day claimed by the person
    orp = DeadlineRule("chosen_date", {"from_fact": "work.unemployment.first_claimed_day", "sources": [1]})
    assert compute_deadline(orp, VD, {"chosen_date": "2026-11-02"})["due"] == "2026-11-02"
    claimed = [Fact("u1", "s_vd", "work.unemployment.first_claimed_day", "2026-12-01", status="confirmed")]
    assert compute_deadline(orp, VD, {"facts": claimed})["due"] == "2026-12-01"
    assert compute_deadline(DeadlineRule("chosen_date"), VD, {})["missing"] == ["chosen_date"]


def check_dossier():
    # reference case: persona Noa, 3 institutions declared, 2 statements 2025 received → Talbruck missing
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "ordner.db")
        sid = demo_seed.seed(store)
        subject, facts, docs = store.get_subject(sid), store.facts(sid), store.documents(sid)
        store.db.close()
    r = completeness(get_card("tax.return.VD"), subject, facts, docs, "2025")
    assert r["status"] == "incomplete" and demo_seed.MANIFEST["missing"][0] in r["missing_documents"], r
    assert [d["issuer"] for d in r["missing_documents"] if d["kind"] == "swiss_tax_statement_eCH0196"] == ["Talbruck Banque Privée SA"]
    assert not any(d["kind"] == "pillar3a_certificate" for d in r["missing_documents"])  # waived: no pillar 3a (confirmed)
    c = consolidate(facts, "2025")
    assert c["status"] == "incomplete" and c["institutions_missing"] == ["Talbruck Banque Privée SA"], c
    assert c["institutions_included"] == ["Morvessa Banque SA", "Zelfeld Courtage SA"]
    ttv = c["totals"]["total_tax_value"]
    zelfeld_page = next(d for d in demo_seed.MANIFEST["documents"] if d["issuer"] == "Zelfeld Courtage SA")["page"]
    assert ttv["status"] == "provisional" and ttv["total"] == round(9288.08 + float(zelfeld_page["totalTaxValue"]), 2), ttv
    assert ttv["by_institution"]["Zelfeld Courtage SA"]["status"] == "proposed"
    # synthetic: wrong year, duplicates, undeclared institutions, connector + seed keys counted once, final totals
    one = Subject("s1", "person", "P", canton="VD")
    inst = lambda status="confirmed": Fact("i", "s1", "finance.institutions", [{"name": "Alpha Bank AG"}], period="2025", status=status)
    stmt = lambda i, year, sha, issuer="Alpha Bank AG": Document(i, "s1", f"/x/{i}.pdf", sha, kind="swiss_tax_statement_eCH0196", year=year, issuer=issuer)
    need = card({})
    need.required_documents = ["swiss_tax_statement_eCH0196"]
    r = completeness(need, one, [inst()], [stmt("d1", 2024, "a"), stmt("d2", 2025, "b"), stmt("d3", 2025, "b"), stmt("d4", 2025, "c")], "2025")
    assert r["status"] == "complete" and r["wrong_year"][0]["document"] == "d1", r
    assert [x["documents"] for x in r["duplicates"]] == [["d2", "d3"], ["d2", "d4"]]
    assert completeness(need, one, [inst()], [stmt("d1", 2024, "a")], "2025")["status"] == "incomplete"
    assert completeness(need, one, [], [stmt("d2", 2025, "b")], "2025")["status"] == "missing_info"
    assert completeness(need, one, [inst("proposed")], [], "2025")["missing_facts"] == ["finance.institutions"]
    both = [inst(), Fact("a", "s1", "tax.statement.total_tax_value.alpha_bank_ag", 100.5, period="2025", status="confirmed"),
            Fact("b", "s1", "tax.securities.alpha.total_tax_value", 100.5, period="2025", status="confirmed")]
    c = consolidate(both, "2025")
    assert c["status"] == "final" and c["totals"]["total_tax_value"]["total"] == 100.5 and c["institutions_missing"] == [], c
    try:
        consolidate(both + [Fact("z", "s2", "tax.statement.total_tax_value.x", 1, period="2025", status="confirmed")], "2025")
        raise AssertionError("mixed subjects accepted")
    except ValueError:
        pass


def main():
    assert DEADLINE_RULE_IDS == ["fixed_date", "days_after_notification", "debt_collection", "reception_by", "cantonal_table",
                                 "year_end", "chosen_date"]
    checks = [check_calendar, check_debt_collection, check_days_after_notification, check_fixed_dates, check_missing_info,
              check_applicability, check_card_params, check_dossier, check_reminders_and_ics]
    for check in checks:
        check()
        print(f"ok  {check.__name__}")
    print(f"ordner.rules selfcheck: {len(checks)} groups passed")


if __name__ == "__main__":
    main()
