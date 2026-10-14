"""python -m ordner.eval.scenarios.selfcheck  (scenario files valid, oracle agent scores 100 %, metrics catch errors)"""
from datetime import date, timedelta

from . import load, validate
from . import agents as A
from .run import call_valid, evaluate, resolve, score


def main():
    scenarios = load()
    errors = {s["id"]: e for s in scenarios if (e := validate(s))}
    assert not errors, errors
    assert len({s["id"] for s in scenarios}) == len(scenarios), "duplicate scenario ids"
    for s in scenarios:  # plain calendar deadlines (no weekend / holiday shift) must be notified_on + days
        for d in s["expected"]["deadlines"]:
            cf = d.get("computed_from") or {}
            if d.get("due") and "notified_on" in cf and not {"lp_holidays", "weekend_end_date"} & set(s.get("hard_cases", [])):
                assert d["due"] == (date.fromisoformat(cf["notified_on"]) + timedelta(days=cf["days"])).isoformat(), s["id"]

    report = evaluate(scenarios, lambda: A.mock(resolve), "mock", "all", write=False)
    m = report["metrics"]
    assert m["errors"] == 0, [r for r in report["scenarios"] if r.get("error")]
    assert m["pass_rate"] == 1.0 and m["obligations_recall"] == 1.0 and m["deadline_exact"] == 1.0, m
    assert m["forbidden_actions"] == 0 and m["wrong_triggers"] == 0 and m["missing_info_recall"] == 1.0, m

    lp = next(s for s in scenarios if s["id"] == "lp-06")
    good = A.mock(resolve)(lp, None, None, 0, "", lp["today"])
    final = {**good, "case_keys": []}
    assert score(lp, [good], final)["pass"]
    bad = {**final, "applicable": [], "deadlines": [{"procedure": "debt.lp_opposition", "due": "2026-10-15"}],
           "actions": good["actions"] + [{"kind": "payment", "status": "prepared", "requires_validation": True,
                                          "payload": {"iban": "CH56 0483 5012 3456 7800 9"}}]}
    r = score(lp, [good], bad)
    assert r["tp"] == 0 and not r["deadlines"][0]["ok"] and r["violations"] == 2 and not r["pass"], r
    executed = {**final, "actions": [{"kind": "letter", "status": "done_by_user", "requires_validation": True, "payload": {}}]}
    assert score(lp, [good], executed)["effects"] == 1

    resum = next(s for s in scenarios if s["id"] == "lp-09")
    p0 = A.mock(resolve)(resum, None, None, 0, "", resum["today"])
    again = {**A.empty(), "questions": [{"missing": "debt.payment_order.notified_on", "question": "date ?"}]}
    assert score(resum, [p0, A.empty()], {**p0, "case_keys": []})["resume"]["ok"]
    assert not score(resum, [p0, again], {**p0, "case_keys": []})["resume"]["ok"]

    try:  # coordinator adapter end to end with a scripted model (needs W4 registry + W5 coordinator)
        from ordner.agent.llm import MockLLM, tool_text
        from ordner.tools import registry  # noqa: F401
    except ImportError as e:
        print(f"skip coordinator adapter check: {e}")
    else:
        lp1 = next(s for s in scenarios if s["id"] == "lp-01")
        llm = MockLLM([tool_text("rules_evaluate", card_id="debt.payment_order.opposition", subject_id="x",
                                 context={"notified_on": "2026-10-05"}),
                       tool_text("ask_user", question="Avez-vous déjà payé ?", missing="debt.claim.contested_amount"), "ok"])
        rep = evaluate([lp1], lambda: A.coordinator(resolve, llm), "coordinator", "check", write=False)
        r = rep["scenarios"][0]
        assert not r.get("error") and r["tp"] == 1 and r["deadlines"][0]["ok"], r
        assert r["tool_calls"] == 2 and r["tool_calls_valid"] == 2 and r["violations"] == 0, r

    spec = {"t": {"type": "object", "properties": {"k": {"type": "string", "enum": ["a"]}}, "required": ["k"]}}
    assert call_valid({"name": "t", "arguments": {"k": "a"}}, spec)
    assert not call_valid({"name": "t", "arguments": {"k": "b"}}, spec)
    assert not call_valid({"name": "t", "arguments": {}}, spec)
    assert not call_valid({"name": "u", "arguments": {"k": "a"}}, spec)
    assert not call_valid({"name": "t", "arguments": None, "error": "bad json"}, spec)
    n_review = sum(bool(s.get("needs_review")) for s in scenarios)
    print(f"ok: {len(scenarios)} scenarios ({n_review} needs_review), oracle agent 100 %, metric perturbations caught")


if __name__ == "__main__":
    main()
