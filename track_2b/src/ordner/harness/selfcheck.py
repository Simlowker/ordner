"""python -m ordner.harness.selfcheck  (scripted Apertus raw-text mock, no weights; ~30 s with the harness build)

1. Proxy units: prefix strip + order, history arguments, runtime-context drop, stop rules, parse-error routing,
   fail-closed refusal of a foreign tool (HTTP 400).
2. End to end on 5 dev scenarios, coordinator vs harness with the same scripted model: identical model inputs at
   every step (messages modulo call ids, tools), identical scores, no silent failure, system prompt = coordinator's.
3. Without translation (the spike setup) the same model gives silent failures and runs no tool.
4. Experts (web UI): definitions and generated presets, routing by marker (tools, adapter; plan Review Focus 1, 2, 3,
   5: foreign tool refused or answered unknown_tool, no marker -> base model, no adapter/MLX -> no `adapters` field,
   backend down -> 502 within the client timeout), web overlay rows and its composition (`dsh --dump-config`).
5. General preset: the router's pick (stubbed d1 service), EmbeddingGemma fallback when the router fails, general when
   nobody is confident, the pick kept for the conversation, at most 3 delimited passages, tool calls and tool results
   untouched, adapters only where use_adapter.
Part 2-3 and the composition are skipped when the harness build is missing (work/vendor/deepseek-harness).
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

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


def check_experts():
    from ordner.tools.registry import SPECS

    from . import experts as E
    names = {s.name for s in SPECS}
    assert set(E.EXPERTS) == {"coordinateur", "impots", "lamal", "poursuites", "logement"}
    for e in E.EXPERTS.values():
        assert e.tools and set(e.tools) <= names, (e.id, set(e.tools) - names)
        sp = E.system_prompt(e.id)
        assert sp.splitlines()[0] == f"[ordner-expert: {e.id}]" and "{{" not in sp   # persona templates are strict
        assert E.marker(sp) == e.id
    assert E.marker("no marker here") is None and E.marker("[ordner-expert: nobody]\nx") is None
    y = E.presets_yaml()
    for e in E.EXPERTS.values():
        row = "preset-standard" if e.id == "coordinateur" else f"preset-{e.id}"
        assert f"- id: {row}\n" in y and f"ORDNER_SYSTEM_{e.id.upper()}" in y and f"ORDNER_MCP_ARGS_{e.id.upper()}" in y
    env = E.env_for("/x/ordner.db", "subj", "2026-02-20", "/s")
    outs = set()
    for e in E.EXPERTS.values():   # Review Focus 4: one MCP process and one state file per expert
        args = json.loads(env[f"ORDNER_MCP_ARGS_{e.id.upper()}"])
        assert args[args.index("--tools") + 1].split(",") == list(e.tools) and "--today" in args
        outs.add(args[args.index("--out") + 1])
        assert env[f"ORDNER_SYSTEM_{e.id.upper()}"] == E.system_prompt(e.id)
    assert outs == {f"/s/state-{i}.json" for i in E.EXPERTS}
    print(f"experts: {len(E.EXPERTS)} presets, tools from the registry, markers, one state file each: ok")


def check_web_patch():
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    from . import experts as E
    from . import runtime as H
    from . import web as W
    text = W.PATCH.read_text(encoding="utf-8")
    assert "dsh-mcp-client" not in text, "web profile: MCP is mounted per expert preset, not at the host"
    for row in ("preset-ptc", "preset-minimal", "preset-cordis", "web", "ui-sidebar-terminal", "terminal-controller",
                "office-to-pdf", "ui-sidebar-documentpreview"):
        assert f"- id: {row}\n  disabled: true" in text, row
    assert "preference: light" in text and "preference: fr" in text
    assert "- id: ui-model-selection\n  disabled: true" in text   # one model: the person picks an expert
    if not H.available():
        return print("web patch: composition SKIPPED (no harness build)")
    with tempfile.TemporaryDirectory() as tmp:
        presets = Path(tmp) / "experts.patch.yml"
        presets.write_text(E.presets_yaml(), encoding="utf-8")
        p = subprocess.run(["node", str(W.BIN), "--profile", "web", "--patch", str(W.PATCH), "--patch", str(presets),
                            "--dump-config"], capture_output=True, text=True, timeout=120,
                           env={**os.environ, "DSH_HOME": tmp})
    assert p.returncode == 0, p.stderr[-2000:]
    tree = p.stdout
    for e in E.EXPERTS.values():
        assert f"ORDNER_MCP_ARGS_{e.id.upper()}" in tree, e.id
    print("web patch: rows off, light/fr, composes with the 5 expert presets (dsh --dump-config exit 0): ok")


def check_routing():
    import socket
    import tempfile
    from pathlib import Path
    from unittest import mock

    from ordner.agent.llm import OpenAICompat

    from . import experts as E
    from .proxy import route
    api = lambda e: {t.replace(".", "_") for t in E.EXPERTS[e].tools} | {"ask_user", "prepare_action"}  # noqa: E731
    sp = E.system_prompt("poursuites")
    r = route([{"role": "system", "content": sp}], adapters_ok=True)
    assert r["expert"] == "poursuites" and set(r["allowed"]) == api("poursuites")
    # Review Focus 2: no marker or an unknown expert -> base model, no adapter, the proxy's own allowlist
    for text in ("plain", "[ordner-expert: nobody]\n" + SYSTEM):
        assert route([{"role": "system", "content": text}], adapters_ok=True) == {"expert": None, "allowed": None,
                                                                                    "adapter": None}
    # Review Focus 3: adapter only if the expert uses it (beat the base on dev), its directory exists and the backend
    # is MLX
    assert {e.id for e in E.EXPERTS.values() if e.use_adapter} == {"poursuites", "logement"}
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(E, "ADAPTERS", Path(tmp)):
        assert route([{"role": "system", "content": sp}], adapters_ok=True)["adapter"] is None   # not trained
        for e in E.EXPERTS.values():
            (Path(tmp) / e.adapter).mkdir()
            (Path(tmp) / e.adapter / "adapters.safetensors").write_bytes(b"")
        d = Path(tmp) / E.EXPERTS["poursuites"].adapter
        assert route([{"role": "system", "content": sp}], adapters_ok=True)["adapter"] == str(d)
        assert route([{"role": "system", "content": sp}], adapters_ok=False)["adapter"] is None   # non-MLX backend
        assert route([{"role": "system", "content": E.system_prompt("lamal")}], adapters_ok=True)["adapter"] is None
        assert E.model_label("poursuites") == "Apertus 1.5 8B + adaptateur expert-poursuites-v1"
        assert E.model_label("lamal") == E.model_label("coordinateur") == "Apertus 1.5 8B"   # trained, not used

        tool = lambda n: {"type": "function", "function": {"name": PREFIX + n, "description": "", "parameters": {}}}  # noqa: E731
        def req(expert, names, system=None):
            return json.dumps({"messages": [{"role": "system", "content": system or E.system_prompt(expert)},
                                            {"role": "user", "content": "Où en est mon dossier ?"}],
                               "tools": [tool(n) for n in names]}).encode()

        def post(p, body):
            try:
                with urllib.request.urlopen(urllib.request.Request(p.url + "/chat/completions", body), timeout=10) as f:
                    return 200, json.load(f)
            except urllib.error.HTTPError as e:
                return e.code, json.load(e)
        up = Upstream()
        allowed = sorted({n for e in E.EXPERTS for n in api(e)})
        with up, Proxy(OpenAICompat(up.url), allowed=allowed, experts=True) as p:
            code, _ = post(p, req("poursuites", sorted(api("poursuites"))))
            assert code == 200 and up.bodies[-1]["adapters"] == str(d) and p.log[-1]["adapter"] == str(d)
            code, _ = post(p, req("impots", sorted(api("impots"))))   # impots: trained, not used (use_adapter)
            assert code == 200 and "adapters" not in up.bodies[-1] and p.log[-1]["adapter"] == "none"
            p.adapters_ok = False   # a jury's own endpoint (vLLM, ...): never an `adapters` field
            code, _ = post(p, req("poursuites", sorted(api("poursuites"))))
            assert code == 200 and "adapters" not in up.bodies[-1] and p.log[-1]["adapter"] == "none"
            p.adapters_ok = True
            code, _ = post(p, req("lamal", ["case_load"], system="plain"))   # Review Focus 2 through the proxy
            assert code == 200 and p.log[-1]["expert"] is None and p.log[-1]["adapter"] == "none"
            assert "adapters" not in up.bodies[-1]
            # Review Focus 1: a request listing a tool of another expert is refused before the model ...
            n = len(up.bodies)
            code, _ = post(p, req("impots", sorted(api("impots") | {"lamal_revoir_franchise"})))
            assert code == 400 and p.log[-1]["refused"] == ["lamal_revoir_franchise"] and len(up.bodies) == n
            # ... and a call the model writes to it goes through the carrier, answered "unknown tool" by the
            # expert's MCP server (Ordner's usual error path); the session goes on.
            up.reply = calls(("lamal_revoir_franchise", {"deductible": 2500}))
            code, out = post(p, req("impots", sorted(api("impots"))))
            (c,) = out["choices"][0]["message"]["tool_calls"]
            assert code == 200 and c["function"]["name"] == PREFIX + CARRIER
            assert json.loads(c["function"]["arguments"])[NAME_KEY] == "lamal_revoir_franchise"
        assert "unknown tool lamal_revoir_franchise" in mcp_answer("impots", c)
        # Review Focus 5: backend down or silent -> HTTP 502 with the error, bounded by the client timeout
        dead = socket.socket()
        dead.bind(("127.0.0.1", 0))
        dead.listen()   # accepts in the backlog, never answers
        port = dead.getsockname()[1]
        with Proxy(OpenAICompat(f"http://127.0.0.1:{port}/v1", timeout=1), experts=True) as p:
            t = time.time()
            code, err = post(p, req("lamal", sorted(api("lamal"))))
            assert code == 502 and "backend error" in err["error"]["message"] and time.time() - t < 5
        dead.close()
        with Proxy(OpenAICompat(f"http://127.0.0.1:{port}/v1", timeout=1), experts=True) as p:   # nothing listens
            code, err = post(p, req("lamal", sorted(api("lamal"))))
            assert code == 502 and p.log[-1]["error"]
    print("routing: marker -> tools + adapter; none without marker/adapter/MLX; foreign tool refused or answered "
          "unknown_tool; backend down -> 502: ok")


def check_general_routing():
    import os
    import socket
    import tempfile
    from pathlib import Path
    from unittest import mock

    import numpy as np

    from ordner.agent.llm import OpenAICompat
    from ordner.explain import retrieve

    from . import experts as E
    from . import router as R
    from .proxy import BANNER, SOURCES_HEAD
    assert set(R.ROUTES) == set(E.EXPERTS)
    assert E.EXPERTS["coordinateur"].name == "Ordner (général)" and "choisit l'expert pour vous" in E.presets_yaml()
    assert R.decide({"lamal": 0.6, "coordinateur": 0.4}, "x")["expert"] == "lamal"
    assert R.decide({"lamal": 0.45, "impots": 0.3, "coordinateur": 0.25}, "x")["expert"] is None   # not confident
    assert R.decide({"lamal": 0.1, "coordinateur": 0.9}, "x")["expert"] is None
    assert BANNER.sub("", "Expert : je pense que oui") == "Expert : je pense que oui"
    api = lambda e: {t.replace(".", "_") for t in E.EXPERTS[e].tools} | {"ask_user", "prepare_action"}  # noqa: E731
    coord = sorted(api("coordinateur"))
    tool = lambda n: {"type": "function", "function": {"name": PREFIX + n, "description": "", "parameters": {}}}  # noqa: E731
    question = "J'ai reçu un commandement de payer, que dois-je faire ?"

    def req(history=()):
        return {"messages": [{"role": "system", "content": E.system_prompt("coordinateur")},
                             {"role": "user", "content": question}, *history], "tools": [tool(n) for n in coord]}

    def post(p, body):
        with urllib.request.urlopen(urllib.request.Request(p.url + "/chat/completions", json.dumps(body).encode()),
                                    timeout=20) as f:
            return json.load(f)["choices"][0]["message"]

    def model_input(p):
        return p.log[-1]["messages"], [t["function"]["name"] for t in p.log[-1]["tools"]]
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    dead_url = f"http://127.0.0.1:{dead.getsockname()[1]}"
    dead.close()   # nothing listens: connection refused
    rank = lambda q, ps: np.arange(len(ps), dtype=float)  # noqa: E731  (stub EmbeddingGemma: later passages first)
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(E, "ADAPTERS", Path(tmp)), \
            mock.patch.object(retrieve, "scores", rank), Upstream() as up, Upstream() as d1:
        for e in E.EXPERTS.values():
            (Path(tmp) / e.adapter).mkdir()
            (Path(tmp) / e.adapter / "adapters.safetensors").write_bytes(b"")
        d1.answer = {"expert": "poursuites", "p": {"poursuites": 0.97, "coordinateur": 0.03}, "by": "d1-3B"}
        up.reply = "Je regarde votre dossier. " + calls(("case_load", {}))
        env = {"ORDNER_EMBED": "1", "ORDNER_ROUTER_URL": d1.url.removesuffix("/v1")}
        with mock.patch.dict(os.environ, env), Proxy(OpenAICompat(up.url), allowed=coord, experts=True,
                                                     canton="VD") as p:
            first = post(p, req())
            msgs, names = model_input(p)
            assert len(d1.bodies) == 1 and d1.bodies[0] == {"text": question}
            assert first["content"] == p.log[-1]["reply"]["content"]   # a step with tool calls: no banner
            assert msgs[0]["content"] == E.system_prompt("poursuites") and up.bodies[-1]["adapters"].endswith(
                "expert-poursuites-v1")
            assert names == [n for n in coord if n in api("poursuites")] and "lamal_revoir_franchise" not in names
            src = [m for m in msgs if m["content"].startswith(SOURCES_HEAD)]
            assert len(src) == 1 and msgs.index(src[0]) == 2 and src[0]["role"] == "user"   # right after the question
            text = src[0]["content"]
            assert "<<<SOURCES" in text and text.endswith("SOURCES>>>") and "[3]" in text and "[4]" not in text
            assert len(p.log[-1]["sources"]) == 3 and all(x.startswith("debt.") for x in p.log[-1]["sources"])
            with Proxy(OpenAICompat(up.url), allowed=coord) as plain:   # same reply, no routing: same tool calls
                assert post(plain, req())["tool_calls"] == first["tool_calls"]
            # the first answer names the expert; the pick is kept (the router is not asked again, even if it would
            # now answer otherwise); the tool result reaches the model unchanged
            d1.answer = {"expert": "lamal", "p": {"lamal": 0.99}, "by": "d1-3B"}
            (c,) = first["tool_calls"]
            result = '{"tool": "case_load", "result": {"subject": "x"}}'
            history = [{"role": "assistant", "content": first["content"], "tool_calls": [c]},
                       {"role": "tool", "tool_call_id": c["id"], "content": result}]
            up.reply = "Vous avez 10 jours pour faire opposition."
            second = post(p, req(history))
            msgs, names = model_input(p)
            assert second["content"] == f"Expert : Poursuites — choisi par d1-3B (97 %)\n\n{up.reply}"
            assert len(d1.bodies) == 1 and p.log[-1]["expert"] == "poursuites"
            assert [m["content"] for m in msgs if m["role"] == "tool"] == [result]
            # next turn: no banner again, the banner is out of the history the model sees, sources after the new message
            history += [{"role": "assistant", "content": second["content"]}, {"role": "user", "content": "Et après ?"}]
            up.reply = "Le créancier peut demander la mainlevée."
            third = post(p, req(history))
            msgs, names = model_input(p)
            assert third["content"] == up.reply and len(d1.bodies) == 1 and p.log[-1]["expert"] == "poursuites"
            assert [m["content"] for m in msgs if m["role"] == "assistant"] == [first["content"],
                                                                                "Vous avez 10 jours pour faire opposition."]
            assert [m["content"] for m in msgs if m["role"] == "tool"] == [result]
            assert [m["tool_calls"][0]["function"]["name"] for m in msgs if m.get("tool_calls")] == ["case_load"]
            assert msgs[-2]["content"] == "Et après ?" and msgs[-1]["content"].startswith(SOURCES_HEAD)
            assert sum(m["content"].startswith(SOURCES_HEAD) for m in msgs) == 1
        up.reply = "Réponse."
        # the router fails -> EmbeddingGemma (stubbed scores); nobody confident -> general, coordinator as is
        for scores, expert in (({"logement": 0.8, "coordinateur": 0.2}, "logement"),
                               ({k: 0.2 for k in R.ROUTES}, None)):
            env = {"ORDNER_EMBED": "1", "ORDNER_ROUTER_URL": dead_url}
            with mock.patch.dict(os.environ, env), mock.patch.object(R, "embed_scores", lambda t, s=scores: s), \
                    Proxy(OpenAICompat(up.url), allowed=coord, experts=True) as p:
                out = post(p, req())
                msgs, names = model_input(p)
                pick = p.log[-1]["routing"]
                assert pick["by"] == "EmbeddingGemma" and pick["expert"] == expert and pick["errors"]
                if expert:
                    assert out["content"].startswith("Expert : Logement et ménage — choisi par EmbeddingGemma (80 %)")
                    assert up.bodies[-1]["adapters"].endswith("expert-logement-v1")
                else:
                    assert out["content"].startswith("Expert : Ordner (général) — aucun expert assez sûr selon "
                                                     "EmbeddingGemma")
                    assert msgs[0]["content"] == E.system_prompt("coordinateur") and names == coord
                    assert "adapters" not in up.bodies[-1] and len(p.log[-1]["sources"]) == 3
        # without ORDNER_EMBED and without router: general, no embedding model loaded, no sources
        with mock.patch.dict(os.environ, {"ORDNER_ROUTER_URL": dead_url}):   # restores ORDNER_EMBED on exit
            os.environ.pop("ORDNER_EMBED", None)
            with Proxy(OpenAICompat(up.url), allowed=coord, experts=True) as p:
                out = post(p, req())
                assert out["content"].startswith("Expert : Ordner (général) — routage indisponible")
                assert p.log[-1]["routing"]["by"] is None and "sources" not in p.log[-1]
    print("general preset: router pick + banner, EmbeddingGemma fallback, general when unsure, pick kept, 3 delimited "
          "passages after the question, tool calls/results untouched: ok")


class Upstream(HTTPServer):
    """Fake OpenAI-compatible backend (or, with `answer`, any JSON endpoint: the d1 router) recording request bodies."""

    def __init__(self):
        class H(BaseHTTPRequestHandler):
            def do_POST(h):
                self.bodies.append(json.loads(h.rfile.read(int(h.headers["Content-Length"]))))
                data = json.dumps(self.answer or {"choices": [{"message": {"role": "assistant",
                                                                           "content": self.reply}}]}).encode()
                h.send_response(200)
                h.send_header("Content-Length", str(len(data)))
                h.end_headers()
                h.wfile.write(data)

            def log_message(h, *a):
                pass
        super().__init__(("127.0.0.1", 0), H)
        self.bodies, self.reply, self.answer = [], "Réponse.", None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/v1"

    def __enter__(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.shutdown()
        self.server_close()


def mcp_answer(expert_id, call):
    """What the expert's own MCP server (its --tools subset) answers to a proxied call."""
    import argparse
    import tempfile
    from pathlib import Path

    from ordner.case import demo_seed
    from ordner.case.store import Store

    from . import experts as E
    from .mcp_server import Server
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "ordner.db"
        sid = demo_seed.seed(Store(db))
        args = json.loads(E.env_for(db, sid, None, tmp)[f"ORDNER_MCP_ARGS_{expert_id.upper()}"])[2:]
        a = argparse.Namespace(today=None, **{k[2:]: v for k, v in zip(args[::2], args[1::2])})
        return Server(a).call(call["function"]["name"][len(PREFIX):], json.loads(call["function"]["arguments"]))


if __name__ == "__main__":
    units()
    check_experts()
    check_routing()
    check_general_routing()
    check_web_patch()
    end_to_end()
    print("harness selfcheck: OK")
