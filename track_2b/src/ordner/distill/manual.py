"""Ceiling check without an API: a Claude Code agent plays the teacher turn by turn, in the same loop as teacher.py
(run_variant, expert mode, process toolset: same prompt, tools, dossier, step budget, scoring). Its trajectories never
train Apertus (filter.NEVER_TRAIN). The score is not shown to the agent.

    cd track_2b; export PYTHONPATH=src
    .venv/bin/python -m ordner.distill.manual start <variant_id>           # starts the loop, prints the first prompt
    .venv/bin/python -m ordner.distill.manual send <variant_id> <<'EOF'     # one reply; prints what comes back
    {"content": "...", "tool_calls": [{"name": "case_load", "arguments": {"subject_id": "..."}}]}
    EOF
    .venv/bin/python -m ordner.distill.manual collect                       # -> work/distill/pilot.claude-code.jsonl

A reply without tool_calls is the final answer. Turn files: work/manual/<variant_id>/.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ordner.agent.llm import _call

from . import OUT, read_jsonl

DIR = Path("work/manual")
VARIANTS = OUT / "pilot24.jsonl"


class FileLLM:
    def __init__(self, d):
        self.d, self.k = d, 0

    def chat(self, messages, tools=None):
        (self.d / f"req{self.k}.json").write_text(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False,
                                                             default=str))
        rep = self.d / f"rep{self.k}.json"
        for _ in range(3600):
            if rep.exists():
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("no reply in 30 min")
        r = json.loads(rep.read_text())
        self.k += 1
        calls = [_call(i, c["name"], c.get("arguments") or {}) for i, c in enumerate(r.get("tool_calls") or [])]
        return {"content": (r.get("content") or "").strip(), "tool_calls": calls, "raw": json.dumps(r, ensure_ascii=False)}


def serve(vid):
    from .teacher import run_variant
    d = DIR / vid
    v = next(v for v in read_jsonl(VARIANTS) if v["id"] == vid)
    row = {"teacher": "claude-code", "model": "claude-opus-5-5 (Claude Code agent)",
           **run_variant(v, FileLLM(d), 12, "process", True)}
    (d / "row.json").write_text(json.dumps(row, ensure_ascii=False, default=str))


def show(d, k):
    """Print request k: the whole prompt at a phase start, else only what was added since request k-1."""
    req = json.loads((d / f"req{k}.json").read_text())
    msgs = req["messages"]
    prev = len(json.loads((d / f"req{k - 1}.json").read_text())["messages"]) if k else 0
    if not k or len(msgs) <= prev:
        print("=== TOOLS ===")
        for t in req["tools"] or []:
            f = t["function"]
            print(f"- {f['name']}: {f.get('description', '')}\n  parameters: {json.dumps(f.get('parameters', {}), ensure_ascii=False)}")
        new = msgs
    else:
        new = [m for m in msgs[prev:] if m["role"] != "assistant"]
    for m in new:
        print(f"=== {m['role'].upper()} ===\n{m.get('content') or ''}")
    print("=== YOUR TURN: send a reply (tool calls, or a final answer without tool calls) ===")


def wait(d, k):
    for _ in range(1200):
        if (d / f"req{k}.json").exists():
            return show(d, k)
        if (d / "row.json").exists():
            return print("=== VARIANT FINISHED ===")
        time.sleep(0.5)
    print("=== no answer from the loop after 10 min: see work/manual/<id>/serve.log ===")


def main():
    cmd, vid = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    d = DIR / (vid or "")
    if cmd == "serve":
        return serve(vid)
    if cmd == "start":
        d.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "ORDNER_EMBED": "1", "TOKENIZERS_PARALLELISM": "false"}
        subprocess.Popen([sys.executable, "-m", "ordner.distill.manual", "serve", vid], env=env,
                         stdout=open(d / "serve.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
        return wait(d, 0)
    if cmd == "send":
        k = len(list(d.glob("rep*.json")))
        reply = json.loads(sys.stdin.read())
        (d / f"rep{k}.json.tmp").write_text(json.dumps(reply, ensure_ascii=False))
        (d / f"rep{k}.json.tmp").rename(d / f"rep{k}.json")
        return wait(d, k + 1)
    if cmd == "collect":
        rows = [json.loads(p.read_text()) for p in sorted(DIR.glob("*/row.json"))]
        (OUT / "pilot.claude-code.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        for r in rows:
            print(("PASS" if (r["score"] or {}).get("pass") else "fail"), r["variant_id"], r["n_calls"], "calls", r["error"] or "")
        print(f"{sum(bool((r['score'] or {}).get('pass')) for r in rows)} / {len(rows)} pass")


if __name__ == "__main__":
    main()
