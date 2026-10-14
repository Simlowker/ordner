"""python -m ordner.harness.selfcheck  (scripted Apertus raw-text mock, no weights; ~30 s with the harness build)

1. Proxy units: prefix strip + order, history arguments, runtime-context drop, stop rules, parse-error routing,
   fail-closed refusal of a foreign tool (HTTP 400).
2. End to end on 5 dev scenarios, coordinator vs harness with the same scripted model: identical model inputs at
   every step (messages modulo call ids, tools), identical scores, no silent failure, system prompt = coordinator's.
3. Without translation (the spike setup) the same model gives silent failures and runs no tool.
Part 2-3 are skipped when the harness build is missing (work/vendor/deepseek-harness, docs/harness_spike.md).
"""
import json
import re
import urllib.error
import urllib.request

from ordner.agent.coordinator import SYSTEM
from ordner.agent.llm import TOOLS_PREFIX, TOOLS_SUFFIX, parse_tool_calls

from .mcp_server import ERROR_KEY, NAME_KEY
from .proxy import CARRIER, PREFIX, Proxy, stop_reason, to_calls, to_model

DEV = ["lp-03", "lp-05", "serafe-04", "move-04", "tax-be-03"]
CARDS = [(r"commandement|zahlungsbefehl|precetto", "debt.payment_order.opposition"),
         (r"déménag|umzug|trasloc", "housing.moving.announce"),
         (r"serafe|redevance|abgabe|canone", "household.serafe_fee"),
         (r"impôt|steuer|impost", "tax.return.BE")]


def calls(*items):
    return f"{TOOLS_PREFIX}{json.dumps([{n: a} for n, a in items], ensure_ascii=False)}{TOOLS_SUFFIX}"


def policy(messages):
    """Scripted Apertus: 2 parallel calls, then ask_user or prepare_action, a duplicate, a malformed call, an answer."""
    goal = messages[1]["content"].split("\n")[0].lower()
    card = next((c for p, c in CARDS if re.search(p, goal)), "tax.return.VD")
    step = sum(m["role"] == "assistant" for m in messages)
    results = [m["content"] for m in messages if m["role"] == "tool"]
    if step == 0:
        return calls(("rules_evaluate", {"card_id": card, "period": "2025"}), ("knowledge_search", {"query": goal[6:80]}))
    if step == 1 and '"status": "missing_info"' in results[0]:
        return "Il me manque une date. " + calls(("ask_user", {"question": "Quand avez-vous reçu le document ?",
                                                                 "missing": "notified_on"}))
    if step == 1:
        return calls(("prepare_action", {"kind": "letter", "summary": f"Lettre ({card})", "amount": 335}))
    if step == 2:
        return calls(("knowledge_search", {"query": goal[6:80]}))   # duplicate: refused by dispatch
    if step == 3:
        return f'{TOOLS_PREFIX}[{{"schedule_plan": {{"due": 2026-08-05}}}}]{TOOLS_SUFFIX}'   # not JSON
    return f"J'ai vérifié {card}. Échéance indicative : 5 août 2026."


class Recorder:
    """Stateless scripted model behind the same parser as the coordinator's clients; records every model input."""

    def __init__(self, policy=policy):
        self.inputs, self.policy = [], policy

    def chat(self, messages, tools=None):
        self.inputs.append((json.loads(json.dumps(messages)), tools))
        raw = self.policy(messages)
        content, tool_calls = parse_tool_calls(raw, {t["function"]["name"] for t in tools or []})
        return {"content": content, "tool_calls": tool_calls, "raw": raw}


def _no_ids(messages):
    """Messages without call ids and with the random dossier ids (new_id: fact_/act_/case_... + 10 hex) masked."""
    out = []
    for m in messages:
        m = {k: v for k, v in m.items() if k != "tool_call_id"}
        if m.get("tool_calls"):
            m["tool_calls"] = [{k: v for k, v in c.items() if k != "id"} for c in m["tool_calls"]]
        out.append(m)
    return json.loads(re.sub(r"\b([a-z]+)_[0-9a-f]{10}\b", r"\1_ID", json.dumps(out, ensure_ascii=False)))


def units():
    tool = lambda n: {"type": "function", "function": {"name": n, "description": "", "parameters": {}}}  # noqa: E731
    req = {"messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "G"},
                        {"role": "user", "content": "Current runtime context. Current working directory: /x"},
                        {"role": "assistant", "content": None, "tool_calls": [
                            {"id": "a", "type": "function", "function": {"name": PREFIX + "case_load", "arguments": "{}"}},
                            {"id": "b", "type": "function", "function": {"name": PREFIX + "case_load",
                                                                         "arguments": json.dumps({ERROR_KEY: "bad"})}},
                            {"id": "c", "type": "function", "function": {"name": PREFIX + CARRIER, "arguments":
                                                                         json.dumps({"to": "x", NAME_KEY: "mail_send"})}}]},
                        {"role": "tool", "tool_call_id": "a", "content": [{"type": "text", "text": "R"}]}],
           "tools": [tool(PREFIX + "prepare_action"), tool(PREFIX + "ask_user"), tool(PREFIX + "case_load")]}
    msgs, tools = to_model(req, order=["case_load", "ask_user", "prepare_action"])
    assert [t["function"]["name"] for t in tools] == ["case_load", "ask_user", "prepare_action"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"] and msgs[2]["content"] == ""
    assert [c["function"]["arguments"] for c in msgs[2]["tool_calls"]] == ['{"_": "invalid"}'] * 2 + ['{"to": "x"}']
    assert [c["function"]["name"] for c in msgs[2]["tool_calls"]] == ["case_load", "case_load", "mail_send"]
    assert msgs[3]["content"] == "R"
    assert len(to_model(req, keep_context=True)[0]) == 5
    asked = {"role": "tool", "content": '{"tool": "ask_user", "result": {"status": "asked", "note": "x"}}'}
    dup = {"role": "tool", "content": '{"tool": "x", "result": {"error": "this exact call was already made: ..."}}'}
    assert stop_reason([asked], 12) == "asked" and stop_reason([dup] * 3, 12) == "duplicates"
    assert stop_reason([dup] * 2, 12) is None and stop_reason([{"role": "assistant", "content": ""}] * 12, 12) == "max_steps"
    _, bad = parse_tool_calls(f'{TOOLS_PREFIX}[{{"schedule_plan": {{"due": 2026-08-05}}}}]{TOOLS_SUFFIX}')
    unknown = [{"name": "mail_send", "arguments": {"to": "x"}, "error": None}]
    c, u = to_calls({"tool_calls": bad + unknown}, PREFIX, 3, {"case_load", CARRIER})
    assert c["function"]["name"] == u["function"]["name"] == PREFIX + CARRIER
    assert json.loads(c["function"]["arguments"]) == {ERROR_KEY: bad[0]["error"], NAME_KEY: None}
    assert json.loads(u["function"]["arguments"]) == {"to": "x", NAME_KEY: "mail_send"}
    with Proxy(Recorder(), allowed=["case_load"]) as p:   # fail closed: a foreign tool in the request
        body = json.dumps({"messages": [], "tools": [tool(PREFIX + "case_load"), tool("bash")]}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(p.url + "/chat/completions", body), timeout=10)
            raise AssertionError("foreign tool accepted")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and p.log[-1]["refused"] == ["bash"] and p.llm.inputs == []
    print("proxy units: ok")


def end_to_end():
    from ordner.eval.scenarios import agents as A
    from ordner.eval.scenarios import load
    from ordner.eval.scenarios.run import evaluate, resolve

    from . import runtime as H
    if not H.available():
        print(f"end to end: SKIPPED (no harness build in {H.HARNESS})")
        return
    scenarios = [s for s in load("dev") if s["id"] in DEV]
    assert len(scenarios) == len(DEV)
    rec_c, rec_h, stats = Recorder(), Recorder(), []
    rep_c = evaluate(scenarios, lambda: A.coordinator(resolve, rec_c), "coordinator_selfcheck", "dev", write=False)

    def make():
        agent = H.scenario_agent(resolve, rec_h)
        return lambda *a: stats.append(out := agent(*a)) or out
    rep_h = evaluate(scenarios, make, "harness_selfcheck", "dev", write=False)
    for rc, rh in zip(rep_c["scenarios"], rep_h["scenarios"]):
        assert not rh.get("error"), rh.get("trace")
        assert {k: v for k, v in rc.items()} == {k: v for k, v in rh.items()}, (rc["id"], rc, rh)
    assert len(rec_c.inputs) == len(rec_h.inputs), (len(rec_c.inputs), len(rec_h.inputs))
    for (mc, tc), (mh, th) in zip(rec_c.inputs, rec_h.inputs):
        assert _no_ids(mc) == _no_ids(mh), json.dumps([_no_ids(mc)[-2:], _no_ids(mh)[-2:]], ensure_ascii=False)[:3000]
        assert tc == th, "tool schemas differ"
    h = [o["harness"] for o in stats]
    assert all(x["prompt_parity"] for x in h) and sum(x["silent_failures"] for x in h) == 0
    assert all(m[0][0] == {"role": "system", "content": SYSTEM} for m in rec_h.inputs)
    print(f"end to end: {len(scenarios)} scenarios, {len(stats)} runs, {len(rec_h.inputs)} model calls, identical model "
          f"inputs and scores; stops {sorted({x['stop'] for x in h}, key=str)}; harness_rejected "
          f"{sum(x['harness_rejected'] for x in h)}; wall {sum(x['wall_s'] for x in h):.1f} s "
          f"({rep_h['metrics']['pass_rate']} pass, same as coordinator {rep_c['metrics']['pass_rate']})")
    loop = lambda m: calls(("knowledge_search", {"query": "délai"}))  # noqa: E731
    for max_steps, stop in ((12, "duplicates"), (2, "max_steps")):   # the coordinator's other loop exits
        rc, rh, st = Recorder(loop), Recorder(loop), []
        c = evaluate(scenarios[:1], lambda: A.coordinator(resolve, rc, max_steps), "c", "dev", write=False)
        agent = H.scenario_agent(resolve, rh, max_steps)
        h = evaluate(scenarios[:1], lambda: lambda *a: st.append(o := agent(*a)) or o, "h", "dev", write=False)
        assert c["scenarios"] == h["scenarios"] and len(rc.inputs) == len(rh.inputs) and st[0]["harness"]["stop"] == stop
        assert [_no_ids(m) for m, _ in rc.inputs] == [_no_ids(m) for m, _ in rh.inputs]
    print("loop exits: duplicates and max_steps stop at the same step as the coordinator")
    raw_stats = []

    def make_raw():
        agent = H.scenario_agent(resolve, Recorder(), raw=True)
        return lambda *a: raw_stats.append(out := agent(*a)) or out
    evaluate(scenarios[:1], make_raw, "harness_raw_selfcheck", "dev", write=False)
    (x,) = [o["harness"] for o in raw_stats]
    assert x["silent_failures"] == 1 and x["executed"] == 0 and x["emitted"] == 0, x
    print(f"no translation (spike setup): silent_failures={x['silent_failures']}, executed={x['executed']}: detected")


if __name__ == "__main__":
    units()
    end_to_end()
    print("harness selfcheck: OK")
