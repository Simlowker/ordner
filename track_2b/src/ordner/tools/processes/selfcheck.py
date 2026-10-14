"""python -m ordner.tools.processes.selfcheck  (replay, no model: Noa Keller persona at 2026-02-20, then dev-split
scenarios through the coordinator adapter with a scripted model and the `process` toolset)."""
import json
import tempfile
from pathlib import Path

from ordner.tools.registry import SPECS, call

from . import NAMES, in_toolset

TODAY = "2026-02-20"


def ok(name, args, ctx):
    r = call(name, args, ctx)
    assert r["ok"], (name, r)
    json.dumps(r)
    d = r["data"]
    assert {"summary", "status", "deadlines", "missing", "questions", "prepared_actions"} <= set(d), (name, d)
    return r


def actions(st, ids):
    return {a.id: a for c in st.cases(st.subjects()[0].id) for a in c.actions if a.id in ids}


def check_noa():
    from ordner.case import Store
    from ordner.case.demo_seed import seed

    with tempfile.TemporaryDirectory() as tmp:
        st = Store(Path(tmp) / "ordner.db")
        sid = seed(st)
        ctx = {"store": st, "subject_id": sid, "today": TODAY, "mode": "replay"}
        docs = {d.issuer: d for d in st.documents(sid)}

        r = ok("piece.recevoir", {"subject_id": sid, "doc": docs["Zelfeld Courtage SA"].id}, ctx)["data"]
        assert r["understood"]["kind"] == "swiss_tax_statement_eCH0196" and "totalTaxValue" in r["doubtful"], r
        assert len(r["facts_proposed"]) == 4 and r["belongs_to"]["card_id"] == "tax.return.VD" and r["questions"], r
        r = ok("piece.recevoir", {"subject_id": sid, "doc": "data/demo/noa/releve_fiscal_2025_morvessa.pdf"}, ctx)["data"]
        assert r["status"] == "duplicate" and r["understood"]["read_path"] == "barcode", r

        r = ok("impots.preparer_declaration", {"subject_id": sid, "period": "2025"}, ctx)["data"]
        dl = r["deadlines"][0]
        assert dl["due"] == "2026-03-15" and dl["extensions"][0]["until"] == "2026-06-30" and dl["sources"], dl
        assert "swiss_tax_statement_eCH0196:Talbruck Banque Privée SA" in r["missing"], r["missing"]
        assert "Talbruck" in r["questions"][0]["question"], r["questions"]
        assert r["totals"]["total_tax_value"] == {"total": 21816.08, "status": "provisional"}, r["totals"]
        acts = actions(st, r["prepared_actions"])
        kinds = sorted(a.kind for a in acts.values())
        assert kinds == ["document_request", "form_entry"] and all(a.requires_validation for a in acts.values()), kinds
        assert any(a.payload.get("recipient") == "Talbruck Banque Privée SA" for a in acts.values())
        assert r["guide"] and all(g["url"] for g in r["guide"]), r["guide"]

        r = ok("lamal.revoir_franchise", {"subject_id": sid, "new_deductible": 2500, "expected_costs": 400}, ctx)
        d = r["data"]
        assert [x["due"] for x in d["deadlines"]] == ["2026-12-31"] and d["deadlines"][0]["variant"] == "higher_deductible"
        assert d["current"]["insurer"].startswith("Helvia") and len(d["prepared_actions"]) == 1, d
        assert d["comparison"] or any("OFSP" in w for w in r["warnings"]), r
        d = ok("lamal.revoir_franchise", {"subject_id": sid}, ctx)["data"]
        assert not d["deadlines"] and sorted(x["due"] for x in d["deadline_options"]) == ["2026-11-30", "2026-12-31"]
        assert d["questions"][0]["missing"] == "health_insurance.change" and not d["prepared_actions"], d

        d = ok("poursuite.repondre", {"subject_id": sid}, ctx)["data"]
        assert d["status"] == "missing_info" and d["questions"][0]["missing"] == "debt.payment_order.notified_on", d
        r = ok("poursuite.repondre", {"subject_id": sid, "notified_on": "2026-02-16", "creditor": "Recouvra SA (fictive)",
                                      "contested_amount": 120.5}, ctx)
        d = r["data"]
        assert d["deadlines"][0]["due"] == "2026-02-26" and "lp_74" in d["deadlines"][0]["sources"], d
        letter = actions(st, d["prepared_actions"])[d["prepared_actions"][0]]
        assert letter.kind == "letter" and "120.50" in letter.payload["body"] and "partielle" in letter.payload["body"]
        assert any("inconnu" in w for w in r["warnings"]), r["warnings"]

        d = ok("demenagement.annoncer", {"subject_id": sid, "move_date": "2027-01-15", "to_canton": "FR",
                                         "to_commune": "Fribourg"}, ctx)["data"]
        due = {(x["card_id"], x.get("kind")): x["due"] for x in d["deadlines"]}
        assert due == {("housing.moving.announce", "departure"): "2027-01-15",
                       ("housing.moving.announce", "arrival"): "2027-01-29",
                       ("tax.return.VD", None): "2027-03-15"}, due
        assert d["applicable"] == ["housing.moving.announce", "tax.return.VD"] and len(d["prepared_actions"]) == 1, d
        assert any("household.serafe_fee#3" in x.get("sources", []) for x in d["tasks"]), d["tasks"]

        for c in st.cases(sid):  # nothing executed, everything waits for the person
            assert all(a.status == "prepared" and a.requires_validation for a in c.actions), c
        st.close()
    print("noa ok: piece, impots, lamal, poursuite, demenagement (replay, today 2026-02-20)")


def scripted(*steps):
    """Mock model: each step is a (tool, args) call, 'ASK' (relay the last tool's first question) or plain text."""
    from ordner.agent.llm import MockLLM, tool_text

    def ask(messages):
        res = json.loads(messages[-1]["content"])["result"]["data"]
        q = res["questions"][0]
        return tool_text("ask_user", question=q["question"], missing=q["missing"])
    return MockLLM([ask if s == "ASK" else tool_text(s[0], **s[1]) if isinstance(s, tuple) else s for s in steps])


def check_scenarios():
    from ordner.eval.scenarios import agents as A
    from ordner.eval.scenarios import load
    from ordner.eval.scenarios.run import evaluate, resolve

    cases = {  # dev split only: the test split is never used to tune tools or prompts
        "lp-03": [("poursuite_repondre", {"subject_id": "x", "notified_on": "2026-07-10"}), "Opposition jusqu'au 05.08.2026."],
        "move-06": [("demenagement_annoncer", {"subject_id": "x", "move_date": "2026-11-03", "to_canton": "VD",
                                               "to_commune": "Renens"}), "Annonce jusqu'au 11.11.2026."],
        "lamal-02": [("lamal_revoir_franchise", {"subject_id": "x", "new_deductible": 2500, "year": 2027}), "ok"],
        "tax-vd-02": [("impots_preparer_declaration", {"subject_id": "x", "period": "2026"}), "ASK"],
    }
    scenarios = {s["id"]: s for s in load("dev")}
    for sid, steps in cases.items():
        s = scenarios[sid]
        rep = evaluate([s], lambda: A.coordinator(resolve, scripted(*steps), toolset="process"), "process", "check",
                       write=False)
        row = rep["scenarios"][0]
        assert not row.get("error") and row["pass"], (sid, row)
        assert row["violations"] == 0 and row["tool_calls_valid"] == row["tool_calls"], (sid, row)
    print(f"scenarios ok (dev, process toolset, scripted model): {', '.join(cases)}")


def main():
    names = {s.name for s in SPECS}
    assert NAMES <= names and not any(s.side_effect for s in SPECS), names
    base = {n for n in names if in_toolset(n, "base")}
    proc = {n for n in names if in_toolset(n, "process")}
    assert not base & NAMES and NAMES <= proc and {n for n in names if in_toolset(n, "both")} == names
    check_noa()
    check_scenarios()


if __name__ == "__main__":
    main()
