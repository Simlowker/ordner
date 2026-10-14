"""Self-check of the distillation pipeline, mock teacher, no network:

    PYTHONPATH=src .venv/bin/python -m ordner.distill.selfcheck [--live]

1. variants: dev-only, seeded (same seed = same variants), no test id/persona/document/goal (leakage assertions)
2. a good mock teacher through the real coordinator loop passes every variant's metrics and the filter keeps it; each
   defective mock (wrong deadline, missed procedure, missing question, invalid tool call, ungrounded date) is rejected
   for its own reason
3. prepare: every turn re-rendered with the Apertus chat template (thinking off) and re-tokenized (see prepare.py),
   no drift, and distill/train.py's dataset gives back exactly prompt and completion around the loss mask
4. no test persona name or test goal in the training text
--live (only if HF_TOKEN / OPENROUTER_API_KEY are set): one variant per teacher, latency, tokens, cost.
"""
import argparse
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ordner.eval.scenarios import load

from . import filter as F
from . import prepare as P
from . import teacher as T
from . import variants as V


def fake_openai_teacher(v):
    """Local stand-in for the HF router / OpenRouter: answers with native OpenAI tool_calls, then plain text."""
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.headers["Authorization"], body))
            if len(seen) == 1:
                msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "x1", "type": "function", "function": {
                    "name": "schedule_plan", "arguments": json.dumps({"due": "2026-12-31"})}}]}
            else:
                msg = {"role": "assistant", "content": "Rien d'autre à faire pour l'instant."}
            out = json.dumps({"choices": [{"message": msg}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out.encode())

        def log_message(self, *_):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = T.run_variant(v, T.Teacher(f"http://127.0.0.1:{srv.server_port}/v1", "fake", "test-key"))
    finally:
        srv.shutdown()
    assert not r["error"] and len(seen) == 2 and seen[0][0] == "Bearer test-key", r["error"]
    hist = seen[1][1]["messages"]
    assert hist[-2]["tool_calls"][0]["id"] == "s1_call_0" and hist[-1]["tool_call_id"] == "s1_call_0"
    call = r["phases"][0]["turns"][0]["reply"]["tool_calls"][0]
    assert (call["name"], call["arguments"]) == ("schedule_plan", {"due": "2026-12-31"}) and r["usage"]["prompt_tokens"] == 200
    return {"teacher": "fake", "model": "fake", **r}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="one real call per teacher whose key is in the environment")
    a = ap.parse_args(argv)

    vs, grounds, _ = V.generate(n=43, seed=11)                  # ~1 per dev scenario
    again, _, _ = V.generate(n=43, seed=11)
    assert json.dumps(vs, sort_keys=True) == json.dumps(again, sort_keys=True), "variants not reproducible"
    test = load("test")
    assert all(v["source_id"] in {s["id"] for s in load("dev")} for v in vs)
    V.leakage(vs, test)
    engine = [v for v in vs if any(p.split(":")[0] in ("canton", "dates", "birth_year") for p in v["perturbations"])]
    print(f"1. {len(vs)} variants, {sum(g[0] for g in grounds.values())}/{len(grounds)} dev scenarios engine-grounded, "
          f"{len(engine)} with engine-recomputed expectations, reproducible, no test leakage")

    good = [{"teacher": "mock", "model": "mock", **T.run_variant(v, T.MockTeacher("good"))} for v in vs]
    bad_keep = [(r["variant_id"], F.reasons(r)) for r in good if F.reasons(r)]
    assert not bad_keep, bad_keep
    expect = {"bad_deadline": ("deadline", lambda v: any(d.get("due") for d in v["expected"]["deadlines"])),
              "bad_missed": ("missed", lambda v: v["expected"]["applicable"]),
              "bad_noask": ("question_not_asked", lambda v: v["expected"].get("missing_info")),
              "bad_invalid": ("invalid_tool_call", lambda v: v["expected"]["applicable"]),
              "bad_date": ("ungrounded_date", lambda v: True)}
    for mode, (reason, applies) in expect.items():
        sample = [v for v in vs if applies(v)][:4]
        assert sample, mode
        for v in sample:
            rs = F.reasons({"teacher": "mock", **T.run_variant(v, T.MockTeacher(mode))})
            assert any(x.startswith(reason) for x in rs), (mode, v["id"], rs)
    print(f"2. good mock kept {len(good)}/{len(good)}; defective mocks rejected: "
          + ", ".join(f"{m} -> {r}" for m, (r, _) in expect.items()))

    native = fake_openai_teacher(vs[0])
    print("2b. OpenAI-compatible teacher with native tool_calls: auth header, unique call ids, usage captured, calls converted")

    with tempfile.TemporaryDirectory() as tmp:
        tok = P.tokenizer()
        stats = P.prepare(good + [native], tok, tmp, valid_share=20)
        assert not stats["drift"] and not stats["dropped_parser_mismatch_or_long_reply"] and not stats["dropped_too_long"], stats
        assert stats["train"] and stats["valid"] and stats["tool_call_turns"] and stats["answer_turns"], stats
        from .train import RawTurns
        rows = [json.loads(x) for f in ("train", "valid") for x in (Path(tmp) / f"{f}.jsonl").read_text().splitlines()]
        ds = RawTurns(rows, tok)
        for r in rows:
            ids, off = ds.process(r)
            assert tok.decode(ids[:off]) == r["prompt_text"] and tok.decode(ids[off:]) == r["completion_text"]
        names = {s["persona"]["name"].casefold() for s in test}
        goals = {g for s in test for ph in [s] + s.get("phases", []) for g in (ph.get("goal") or {}).values()}
        assert not any(n in (r["prompt_text"] + r["completion_text"]).casefold() for r in rows for n in names)
        assert not any(g in r["prompt_text"] for r in rows for g in goals)
    print(f"3. prepare: {stats['train']} train / {stats['valid']} valid turns ({stats['tool_call_turns']} tool calls, "
          f"{stats['answer_turns']} answers), tokens max {stats['tokens_max']} mean {stats['tokens_mean']}; template, "
          "tokenizer, parser and loss-mask round trips OK")
    print("4. no test persona name or goal in the training text")

    for name, t in T.TEACHERS.items():
        if not (a.live and os.environ.get(t["key"])):
            print(f"live {name}: skipped ({t['key']} not set)" if not os.environ.get(t["key"]) else
                  f"live {name}: skipped (pass --live)")
            continue
        v = vs[0]
        r = T.run_variant(v, T.backend(name))
        s = r["score"] or {}
        print(f"live {name} ({t['model']}) on {v['id']}: {r['n_calls']} calls, {r['latency_s']} s, usage {r['usage']}, "
              f"pass {s.get('pass')}, filter {F.reasons({'teacher': name, **r}) or 'kept'}")
    print("distill selfcheck OK")


if __name__ == "__main__":
    main()
