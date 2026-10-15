"""Teacher trajectories: the SAME coordinator loop (ordner.agent.coordinator.run through the scenario runner: same
seeding, tools, prompts, step budget, scoring) driven by a stronger model behind an OpenAI-compatible API.

    set -a; . ./.env; set +a     # HF_TOKEN / OPENROUTER_API_KEY, read from the environment only, never logged
    PYTHONPATH=src .venv/bin/python -m ordner.distill.teacher --teacher apertus70b [--limit 5]
    PYTHONPATH=src .venv/bin/python -m ordner.distill.teacher --teacher glm
    PYTHONPATH=src .venv/bin/python -m ordner.distill.teacher --teacher mock      # plumbing, no network

Output: work/distill/traj.<teacher>.jsonl, one line per variant (appends; variants already present are skipped):
{"variant_id", "source_id", "teacher", "model", "phases": [{"messages", "tools", "turns": [{"n", "reply", "latency_s",
"usage"}]}], "outs", "score", "error", "latency_s", "usage"}. Turn k's prompt is messages[:n] (what the model saw) and
its target is reply (content + tool calls). A teacher answering with native OpenAI tool_calls is converted by the
backend into the same {name, arguments} calls the Apertus text parser yields; prepare.py renders them in Apertus syntax.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

from ordner.agent.llm import TOOLS_PREFIX, TOOLS_SUFFIX, OpenAICompat, _call, _names, parse_tool_calls
from ordner.eval.scenarios import agents as A
from ordner.eval.scenarios import run as R
from ordner.procedures import catalog

from . import OUT, read_jsonl

TEACHERS = {  # checked 14.10.2026: HF router maps swiss-ai/Apertus-v1.5-70B to featherless-ai; OpenRouter id z-ai/glm-5.3
    "apertus70b": {"base_url": "https://router.huggingface.co/v1", "model": "swiss-ai/Apertus-v1.5-70B", "key": "HF_TOKEN"},
    "glm": {"base_url": "https://openrouter.ai/api/v1", "model": "z-ai/glm-5.3", "key": "OPENROUTER_API_KEY",
            "extra": {"usage": {"include": True}}},
    "deepseek": {"base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-v4.1-flash",
                 "key": "OPENROUTER_API_KEY", "extra": {"usage": {"include": True}}},
}


class Teacher(OpenAICompat):
    """OpenAICompat plus usage/latency capture, retries on 429/5xx, unique tool-call ids and extra body fields.
    The API key is only put in the Authorization header."""

    def __init__(self, base_url, model, api_key, extra=None, max_tokens=1024, timeout=300, retries=4):
        super().__init__(base_url, model, api_key, max_tokens, timeout)
        self.extra, self.retries, self.last = extra or {}, retries, {}

    def chat(self, messages, tools=None):
        body = {"model": self.model, "messages": unique_ids(messages), "temperature": 0, "max_tokens": self.max_tokens,
                **self.extra}
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(self.url, json.dumps(body).encode(), {
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        for attempt in range(self.retries + 1):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    resp = json.load(r)
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code not in (408, 429, 500, 502, 503, 504) or attempt == self.retries:
                    raise RuntimeError(f"teacher HTTP {e.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries:
                    raise RuntimeError(f"teacher unreachable: {e}") from None
            time.sleep(2 ** attempt * 3)
        if "choices" not in resp:
            raise RuntimeError(f"teacher returned no choices: {json.dumps(resp)[:300]}")
        msg = resp["choices"][0]["message"]
        self.last = {"usage": resp.get("usage") or {}, "latency_s": round(time.perf_counter() - t0, 2),
                     "provider": resp.get("provider"), "served_model": resp.get("model")}
        raw = msg.get("content") or ""
        if msg.get("tool_calls"):
            calls = [_call(n, c["function"]["name"], c["function"].get("arguments") or "{}")
                     for n, c in enumerate(msg["tool_calls"])]
            return {"content": raw.strip(), "tool_calls": calls, "raw": raw}
        content, calls = parse_tool_calls(raw, _names(tools))   # Apertus text syntax, with or without special tokens
        return {"content": content, "tool_calls": calls, "raw": raw}


def unique_ids(messages):
    """The coordinator numbers tool calls call_0.. at every step; strict APIs want ids unique in the conversation."""
    out, step = [], 0
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            step += 1
            m = {**m, "tool_calls": [{**c, "id": f"s{step}_{c['id']}"} for c in m["tool_calls"]]}
        elif m["role"] == "tool":
            m = {**m, "tool_call_id": f"s{step}_{m['tool_call_id']}"}
        out.append(m)
    return out


class Recorder:
    """Wraps a backend; keeps every prompt (the coordinator's message list) and reply, per phase."""

    def __init__(self, llm):
        self.llm, self.calls, self.phase = llm, [], -1

    def chat(self, messages, tools=None):
        t0 = time.perf_counter()
        reply = self.llm.chat(messages, tools)
        last = getattr(self.llm, "last", {}) or {}
        self.calls.append({"phase": self.phase, "n": len(messages), "messages": messages, "tools": tools,
                           "reply": reply, "latency_s": last.get("latency_s", round(time.perf_counter() - t0, 3)),
                           "usage": last.get("usage")})
        return reply

    def phases(self):
        out = []
        for p in sorted({c["phase"] for c in self.calls}):
            cs = [c for c in self.calls if c["phase"] == p]
            out.append({"messages": json.loads(json.dumps(cs[-1]["messages"], ensure_ascii=False, default=str)),
                        "tools": cs[0]["tools"],
                        "turns": [{k: c[k] for k in ("n", "reply", "latency_s", "usage")} for c in cs]})
        return out


class MockTeacher:
    """Oracle policy from the variant's expected outcome, written as raw Apertus text (same parser as the 8B):
    open the expected cases, record the expected deadlines, prepare the expected actions, ask the expected questions,
    answer. mode != "good" injects one defect (self-check of the filter)."""
    MODES = ("good", "bad_deadline", "bad_missed", "bad_noask", "bad_invalid", "bad_date")

    def __init__(self, mode="good"):
        self.mode, self.v, self.phase, self.step = mode, None, -1, 0

    def begin(self, v):
        self.v, self.phase = v, -1

    def chat(self, messages, tools=None):
        if len(messages) == 2:
            self.phase, self.step = self.phase + 1, 0
        raw = self.policy(messages)
        self.step += 1
        content, calls = parse_tool_calls(raw, _names(tools))
        return {"content": content, "tool_calls": calls, "raw": raw}

    def policy(self, messages):
        v, x, sid = self.v, self.v["expected"], A.subject_id(self.v)
        last = self.phase == len(v.get("phases", []))
        app = [R.resolve(p) for p in x.get("applicable", [])][1 if self.mode == "bad_missed" else 0:]
        if self.step == 0 and app:
            name = "case_write" if self.mode == "bad_invalid" else "case_record"
            return calls([(name, {"subject_id": sid, "op": "open_case", "card_id": p,
                                  **({"period": v["period"]} if v.get("period") else {})}) for p in app])
        if self.step == 1 and app and last:
            cases = opened(messages)
            todo = []
            for d in x.get("deadlines", []):
                p = R.resolve(d["procedure"])
                if d.get("due") and p in cases:
                    due = d["due"] if self.mode != "bad_deadline" else _next_day(d["due"])
                    todo.append(("case_record", {"subject_id": sid, "op": "add_deadline", "case_id": cases[p],
                                                 "due": due, "rule_id": getattr(catalog.get(p).deadline, "id", None) or d.get("rule") or "document"}))
            for k in x.get("actions", []) if cases else []:
                kind = k if isinstance(k, str) else k[0]
                todo.append(("prepare_action", {"kind": kind, "case_id": next(iter(cases.values())),
                                                "summary": f"{kind} prepared for review"}))
            if todo:
                return calls(todo)
            self.step += 1
        asks = [] if self.mode == "bad_noask" or self.phase > 0 else x.get("missing_info", [])
        if asks and (not v.get("phases") or not last):
            return calls([("ask_user", {"question": f"{m['topic']} ?", "missing": m["match"][0]}) for m in asks])
        done = {"fr": "C'est fait : le dossier est à jour, à vous de valider.", "de": "Erledigt: das Dossier ist "
                "aktuell, bitte prüfen.", "it": "Fatto: il dossier è aggiornato, da convalidare."}[v["lang"]]
        return done + (" Échéance : 31.12.2031." if self.mode == "bad_date" else "")


def calls(items):
    return f"{TOOLS_PREFIX}[{', '.join(json.dumps({n: a}, ensure_ascii=False) for n, a in items)}]{TOOLS_SUFFIX}"


def opened(messages):
    """card_id -> case id from the open_case results in the conversation."""
    out = {}
    for m in messages:
        if m["role"] != "tool":
            continue
        try:
            rec = (json.loads(m["content"]).get("result") or {}).get("data") or {}
        except (json.JSONDecodeError, AttributeError):
            continue
        if rec.get("op") == "open_case" and isinstance(rec.get("recorded"), dict):
            out[rec["recorded"]["card_id"]] = rec["recorded"]["id"]
    return out


def _next_day(d):
    from datetime import date, timedelta
    return (date.fromisoformat(d) + timedelta(1)).isoformat()


def backend(name, max_tokens=1024, extra=None, model=None):
    if name.startswith("mock"):
        return MockTeacher(name.split(":", 1)[1] if ":" in name else "good")
    t = TEACHERS[name]
    key = os.environ.get(t["key"])
    if not key:
        raise SystemExit(f"{t['key']} is not set (set -a; . ./.env; set +a)")
    return Teacher(t["base_url"], model or t["model"], key, {**t.get("extra", {}), **(extra or {})}, max_tokens)


def expert_for(v):
    """The variant's domain expert (ordner.harness.experts), "coordinateur" when it spans domains."""
    from ordner.distill.by_expert import expert_of, procedures
    from ordner.harness.experts import EXPERTS
    return expert_of(procedures(v, R.resolve), EXPERTS) or "coordinateur"


def run_variant(v, llm, max_steps=12, toolset="base", expert_mode=False):
    rec = Recorder(llm)
    expert = expert_for(v) if expert_mode else None
    if hasattr(llm, "begin"):
        llm.begin(v)

    def make():
        rec.phase += 1
        return A.coordinator(R.resolve, rec, max_steps, toolset, expert=expert)
    t0, err, outs, row = time.perf_counter(), None, [], None
    try:
        outs, final = R.run_one(v, make)
        row = R.score(v, outs, final)
    except Exception as e:   # one failing variant (API error, tool crash) never stops the batch
        err = f"{type(e).__name__}: {e}"[:500]
    usage = {}
    for c in rec.calls:
        for k, n in (c.get("usage") or {}).items():
            if isinstance(n, (int, float)):
                usage[k] = round(usage.get(k, 0) + n, 6)
    return {"variant_id": v["id"], "source_id": v.get("source_id"), "toolset": toolset, "expert": expert,
            "phases": rec.phases(),
            "outs": [{k: o.get(k) for k in ("applicable", "questions", "deadlines", "actions", "tool_calls", "notes",
                                            "answer", "attempted_effects")} for o in outs],
            "score": row, "error": err, "latency_s": round(time.perf_counter() - t0, 2), "usage": usage,
            "n_calls": len(rec.calls)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--teacher", required=True, help="apertus70b | glm | mock | mock:<mode>")
    ap.add_argument("--model", help="override the teacher model id")
    ap.add_argument("--variants", default=str(OUT / "variants.jsonl"))
    ap.add_argument("--out", help="default work/distill/traj.<teacher>.jsonl")
    ap.add_argument("--only", help="comma-separated variant ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--toolset", choices=["base", "process", "both"], default="base",
                    help="same choice as the runner's --toolset (H6); train and evaluate the student with the same one")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--expert-mode", action="store_true",
                    help="each variant runs as its domain expert, exactly as the web UI (prompt, tools, opening, sources)")
    ap.add_argument("--extra", type=json.loads, default=None, help='extra JSON body fields, e.g. \'{"tool_choice": "auto"}\'')
    a = ap.parse_args(argv)
    out = a.out or str(OUT / f"traj.{a.teacher.replace(':', '-')}{'' if a.toolset == 'base' else '.' + a.toolset}.jsonl")
    variants = read_jsonl(a.variants)
    if a.only:
        variants = [v for v in variants if v["id"] in a.only.split(",")]
    variants = variants[: a.limit]
    done = {r["variant_id"] for r in read_jsonl(out)} if os.path.exists(out) else set()
    llm = backend(a.teacher, a.max_tokens, a.extra, a.model)
    model = getattr(llm, "model", a.teacher) if not a.teacher.startswith("mock") else a.teacher
    os.makedirs(os.path.dirname(out), exist_ok=True)
    new = []
    with open(out, "a", encoding="utf-8") as f:
        for v in variants:
            if v["id"] in done:
                continue
            r = {"teacher": a.teacher, "model": model, **run_variant(v, llm, a.max_steps, a.toolset, a.expert_mode)}
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            f.flush()
            new.append(r)
            s = r["score"] or {}
            print(f"{'PASS' if s.get('pass') else 'fail'} {v['id']} {r['n_calls']} calls {r['latency_s']}s "
                  f"tokens {r['usage'].get('prompt_tokens', '-')}/{r['usage'].get('completion_tokens', '-')}"
                  + (f" cost ${r['usage']['cost']}" if "cost" in r["usage"] else "") + (f"  {r['error']}" if r["error"] else ""),
                  flush=True)
    if new:   # cost / latency per variant, for the report
        tot = lambda k: sum(r["usage"].get(k, 0) for r in new)  # noqa: E731
        print(f"{len(new)} new trajectories -> {out}: pass {sum(bool((r['score'] or {}).get('pass')) for r in new)}, "
              f"errors {sum(bool(r['error']) for r in new)}, latency/variant {sum(r['latency_s'] for r in new) / len(new):.1f} s, "
              f"tokens/variant {tot('prompt_tokens') / len(new):.0f} in + {tot('completion_tokens') / len(new):.0f} out"
              + (f", cost/variant ${tot('cost') / len(new):.4f}" if tot("cost") else ""))


if __name__ == "__main__":
    main()
