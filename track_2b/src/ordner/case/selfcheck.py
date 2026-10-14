"""python -m ordner.case.selfcheck  (temp ORDNER_HOME; asserts on lifecycle, supersede, isolation, transitions,
idempotency, actions, append-only log, snapshot, persistence, demo seed)"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from ordner.core.schema import Action, Deadline, Document, Fact, Subject, new_id

from . import demo_seed
from .store import Store


def raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    raise AssertionError(f"{fn} did not raise {exc.__name__}")


def fact(sid, key, value, period="2025", actor="model", doc=None):
    return Fact(new_id("fact"), sid, key, value, period=period, actor=actor, source_doc=doc)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ORDNER_HOME"] = tmp
        st = Store()
        assert st.path == Path(tmp) / "ordner.db" and st.path.exists()

        # subjects
        a = st.add_subject(Subject("p_a", "person", "Alice", canton="VD"))
        b = st.add_subject(Subject("c_b", "company", "Beta Sàrl", canton="GE"))
        raises(lambda: st.add_subject(Subject("p_a", "person", "Again")))
        raises(lambda: st.add_subject(Subject("x", "alien", "X")))
        raises(lambda: st.get_subject("nobody"), KeyError)

        # documents: idempotent per subject + sha256, separate across subjects
        d1 = st.add_document(Document(new_id("doc"), a.id, "/x/a.pdf", "sha1", kind="tax", year=2025))
        again = st.add_document(Document(new_id("doc"), a.id, "/x/copy.pdf", "sha1", kind="tax", year=2025))
        assert again.id == d1.id and len(st.documents(a.id)) == 1
        assert sum(e.type == "document_received" for e in st.events(a.id)) == 1
        db_ = st.add_document(Document(new_id("doc"), b.id, "/x/b.pdf", "sha1", kind="tax", year=2025))
        assert db_.id != d1.id and [d.id for d in st.documents(b.id)] == [db_.id]
        assert st.documents(a.id, kind="tax", year=2025) and not st.documents(a.id, year=2024)
        raises(lambda: st.documents(None), KeyError)

        # facts: provenance + proposed -> confirmed / rejected
        f1 = st.propose_fact(fact(a.id, "tax.wealth", 100, doc=d1.id))
        assert f1.status == "proposed" and f1.actor == "model" and f1.source_doc == d1.id
        assert f1.confirmed_at is None and f1.confirmed_by is None
        raises(lambda: st.confirm_fact(f1.id, actor="model"))
        f1 = st.confirm_fact(f1.id)
        assert f1.status == "confirmed" and f1.confirmed_by == "user" and f1.confirmed_at
        raises(lambda: st.confirm_fact(f1.id))
        raises(lambda: st.propose_fact(fact(b.id, "tax.wealth", 1, doc=d1.id)))  # A's document for B: refused
        raises(lambda: st.propose_fact(Fact(new_id("fact"), a.id, "k", 1, status="confirmed")))
        r = st.reject_fact(st.propose_fact(fact(a.id, "tax.wealth", 999)).id, actor="connector")
        assert r.status == "rejected" and r.confirmed_by == "connector" and r.confirmed_at

        # supersede: same key + period, history kept; other period / other subject untouched
        f_other_period = st.confirm_fact(st.propose_fact(fact(a.id, "tax.wealth", 80, period="2024")).id)
        f_b = st.confirm_fact(st.propose_fact(fact(b.id, "tax.wealth", 5)).id)
        f2 = st.confirm_fact(st.propose_fact(fact(a.id, "tax.wealth", 120, actor="user")).id)
        assert f2.supersedes == f1.id
        statuses = {f.id: f.status for f in st.facts(a.id, key_prefix="tax.")}
        assert statuses == {f1.id: "superseded", r.id: "rejected", f_other_period.id: "confirmed", f2.id: "confirmed"}
        assert [f.id for f in st.facts(b.id)] == [f_b.id] and st.facts(b.id)[0].status == "confirmed"
        assert [f.value for f in st.facts(a.id, status="confirmed", key_prefix="tax.wealth")] == [80, 120]
        sup = [e for e in st.events(a.id) if e.type == "fact_superseded"]
        assert len(sup) == 1 and sup[0].payload["old_value"] == 100 and sup[0].payload["by"] == f2.id

        # cases: idempotent open, validated transitions, back-transitions need a reason
        c = st.open_case(a.id, "tax.return.VD", "2025")
        assert st.open_case(a.id, "tax.return.VD", "2025").id == c.id
        c_2024 = st.open_case(a.id, "tax.return.VD", "2024")
        assert c_2024.id != c.id
        assert c.state == "to_qualify"
        raises(lambda: st.set_state(c.id, "action_engaged"))
        raises(lambda: st.set_state(c.id, "bogus"))
        st.set_missing(c.id, ["salary_certificate"])
        for s in ["missing_documents", "ready_to_prepare", "ready_to_validate", "action_engaged",
                  "awaiting_response", "complement_requested", "awaiting_response", "decision_received"]:
            assert st.set_state(c.id, s).state == s
        raises(lambda: st.set_state(c.id, "ready_to_prepare"))          # back without reason
        assert st.set_state(c.id, "ready_to_prepare", reason="decision contested, new filing").state == "ready_to_prepare"
        back = [e for e in st.events(case_id=c.id) if e.type == "state_changed"][-1]
        assert back.payload == {"from": "decision_received", "to": "ready_to_prepare",
                                "reason": "decision contested, new filing"}
        c2 = st.open_case(a.id, "lamal.change", "2027")
        raises(lambda: st.set_state(c2.id, "closed"))
        assert st.set_state(c2.id, "closed", reason="not applicable").state == "closed"
        c3 = st.open_case(a.id, "lamal.change", "2027")
        assert c3.id != c2.id                                              # a closed case is not reused

        # actions: validation required before done_by_user, only the user validates, no duplicates
        act = st.add_action(Action(new_id("act"), c.id, "letter", {"to": "ACI VD", "body": "..."}))
        assert act.requires_validation and act.status == "prepared"
        assert st.add_action(Action(new_id("act"), c.id, "letter", {"to": "ACI VD", "body": "..."})).id == act.id
        raises(lambda: st.update_action(act.id, "done_by_user"))
        raises(lambda: st.update_action(act.id, "validated", actor="ordner"))
        st.update_action(act.id, "validated")
        st.update_action(act.id, "done_by_user")
        assert st.update_action(act.id, "verified").status == "verified"
        steps = [e.payload["to"] for e in st.events(case_id=c.id) if e.type == "action_updated"]
        assert steps == ["validated", "done_by_user", "verified"]
        raises(lambda: st.add_action(Action(new_id("act"), c.id, "payment", {"amount": 1}, requires_validation=False)))
        rem = st.add_action(Action(new_id("act"), c.id, "reminder", {"on": "2026-11-01"}, requires_validation=False))
        assert st.update_action(rem.id, "done_by_user", actor="ordner").status == "done_by_user"
        pay = st.add_action(Action(new_id("act"), c.id, "payment", {"amount": 250}))

        # deadlines: same rule + same date = idempotent, new date = recomputation (old one superseded), done
        dl = st.add_deadline(Deadline(new_id("dl"), c.id, "2026-03-15", "fixed_date"))
        assert dl.status == "active"
        assert st.add_deadline(Deadline(new_id("dl"), c.id, "2026-03-15", "fixed_date")).id == dl.id
        ext = st.add_deadline(Deadline(new_id("dl"), c.id, "2026-09-30", "extension"))
        ext2 = st.add_deadline(Deadline(new_id("dl"), c.id, "2026-12-31", "extension"))
        assert [(d.id, d.status) for d in st.deadlines(c.id, status=None) if d.rule_id == "extension"] == [
            (ext.id, "superseded"), (ext2.id, "active")]
        sup_dl = [e.payload for e in st.events(case_id=c.id) if e.type == "deadline_superseded"]
        assert sup_dl == [{"deadline_id": ext.id, "by": ext2.id, "rule_id": "extension", "old_due": "2026-09-30",
                           "new_due": "2026-12-31"}]
        assert [d.id for d in st.get_case(c.id).deadlines] == [dl.id, ext2.id]  # Case.deadlines = active only
        rem_dl = st.add_deadline(Deadline(new_id("dl"), c.id, "2026-11-15", "reminder_rule"))
        assert st.complete_deadline(rem_dl.id).status == "done"
        assert st.add_deadline(Deadline(new_id("dl"), c.id, "2026-11-15", "reminder_rule")).id == rem_dl.id
        raises(lambda: st.complete_deadline(ext.id))
        raises(lambda: st.add_deadline(Deadline(new_id("dl"), c.id, "31.12.2026", "x")))
        raises(lambda: st.add_deadline(Deadline(new_id("dl"), c.id, "2026-12-31", "x", status="done")))

        # append-only log, enforced by the database
        raises(lambda: st.db.execute("UPDATE events SET type='x'"), sqlite3.DatabaseError)
        raises(lambda: st.db.execute("DELETE FROM events"), sqlite3.DatabaseError)
        st.db.rollback()
        types = {e.type for e in st.events(a.id)}
        assert {"document_received", "fact_proposed", "fact_confirmed", "fact_rejected", "fact_superseded",
                "case_opened", "state_changed", "missing_updated", "action_prepared", "action_updated",
                "deadline_added", "deadline_superseded", "deadline_done"} <= types

        # snapshot: plain JSON, complete, no leak across subjects
        snap = st.snapshot(a.id, today="2026-10-14")
        json.dumps(snap)
        assert [x["id"] for x in snap["open_cases"]] == [c.id, c_2024.id, c3.id]
        assert snap["open_cases"][0]["missing"] == ["salary_certificate"]
        assert [x["card_id"] for x in snap["closed_cases"]] == ["lamal.change"]
        assert [(x["due"], x["overdue"]) for x in snap["upcoming_deadlines"]] == [("2026-03-15", True),
                                                                                    ("2026-12-31", False)]
        assert {x["id"] for x in snap["pending_actions"]} == {rem.id, pay.id}
        assert len(snap["facts"]["confirmed"]) == 2 and len(snap["facts"]["superseded"]) == 1
        assert len(snap["last_events"]) == 20
        snap_b = json.dumps(st.snapshot(b.id))
        for leaked in (d1.id, f1.id, f2.id, c.id, act.id, "Alice"):
            assert leaked not in snap_b, leaked

        # persistence: a new Store on the same file resumes the same state
        st.close()
        st = Store(Path(tmp) / "ordner.db")
        assert st.snapshot(a.id, today="2026-10-14") == snap

        # demo seed: idempotent, coherent
        sid = demo_seed.seed(st)
        n = len(st.events(sid))
        assert demo_seed.seed(st, cases=[("tax.return.VD", "2025")]) == sid
        assert len(st.events(sid)) == n + 1  # only the case_opened event
        noa = st.snapshot(sid)
        json.dumps(noa)
        assert noa["subject"]["name"] == "Noa Keller" and noa["subject"]["attrs"]["fictional"]
        assert len(noa["documents"]) == len(demo_seed.DOCS)
        assert {k: len(v) for k, v in noa["facts"].items()} == {"proposed": 7, "confirmed": 19, "rejected": 1,
                                                                "superseded": 1}
        # tax statements: 3 institutions declared, 2 delivered (barcode PDF + AI photo), the real files match the
        # manifest; everything else is an explicit placeholder
        declared = st.facts(sid, key_prefix="finance.institutions", status="confirmed")[0].value
        stmts = st.documents(sid, kind="swiss_tax_statement_eCH0196", year=2025)
        assert len(declared) == 3 and len(stmts) == 2
        assert {d["name"] for d in declared} - {d.issuer for d in stmts} == {"Talbruck Banque Privée SA"}
        assert {d.read_path for d in stmts} == {"barcode", "ai"}
        for d, m in zip(stmts, demo_seed.MANIFEST["documents"]):
            p = Path(d.path)
            assert p.is_file() and d.sha256 == m["sha256"] and p.stat().st_size < (100_000 if p.suffix == ".pdf"
                                                                                       else 300_000)
            assert m["truth"]["client_last_name"] == "Keller" and m["truth"]["canton"] == "VD"
        others = [d for d in st.documents(sid) if d.kind != "swiss_tax_statement_eCH0196"]
        assert others and all(d.path.startswith("placeholder:") for d in others)
        photo = st.facts(sid, key_prefix="tax.securities.zelfeld.total", status="proposed")
        assert photo and photo[0].actor == "model" and photo[0].doubt
        emp = st.facts(sid, key_prefix="work.employment.employer")
        assert [(f.value, f.status) for f in emp] == [("Alpinea Garage Sàrl", "superseded"), ("Logivia SA", "confirmed")]
        assert "Alice" not in json.dumps(noa)
        st.close()
    print("ordner.case selfcheck OK")


if __name__ == "__main__":
    main()
