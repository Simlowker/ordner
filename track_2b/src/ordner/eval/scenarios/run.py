"""python -m ordner.eval.scenarios.run --agent {rules_only,coordinator,mock} --split {dev,test,all}

Runs every scenario on a fresh temporary dossier (ordner.case Store), phase by phase (a fresh agent instance per
phase = resumption after interruption), then scores. Writes data/results/scenarios_<agent>.json and .md.
Scenarios marked needs_review are run and shown but excluded from the metrics.
Coordinator: --llm-url (OpenAI-compatible server with Apertus, default $LLM_BASE_URL) or --llm mock (plumbing test).
"""
import argparse
import json
import os
import sys
import tempfile
import traceback
from collections import defaultdict
from pathlib import Path

from . import HARD_CASES, PROCEDURES, ROOT, load
from . import agents as A

RESULTS = ROOT / "data" / "results"
EFFECT_STATUSES = {"validated", "done_by_user", "verified"}   # reachable only through the person, never the agent

# Canonical scenario id -> catalogue card id, when the catalogue (W2) names a procedure differently.
ALIASES: dict[str, str] = {}


def resolve(pid: str) -> str:
    return ALIASES.get(pid, pid)


def catalogue_ids() -> set | None:
    try:
        from ordner.procedures import catalog
        return {c.id for c in catalog.load_cards()}
    except Exception:
        return None


# -- tool-call schema validity ------------------------------------------------------------------------------------

_TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list}


def call_valid(call: dict, specs: dict) -> bool:
    """Strict top-level check: known tool, JSON parsed, required present, declared types and enums respected."""
    if call.get("error") or call.get("name") not in specs or not isinstance(call.get("arguments"), dict):
        return False
    schema, args = specs[call["name"]], call["arguments"]
    props = schema.get("properties", {})
    if any(args.get(k) in (None, "") for k in schema.get("required", [])):
        return False
    if schema.get("additionalProperties") is False and set(args) - set(props):
        return False
    for k, v in args.items():
        p = props.get(k, {})
        t = _TYPES.get(p.get("type"))
        if t and (not isinstance(v, t) or (isinstance(v, bool) and p.get("type") in ("number", "integer"))):
            return False
        if "enum" in p and v not in p["enum"]:
            return False
    return True


# -- scoring -------------------------------------------------------------------------------------------------------

def _asked(match: list[str], questions: list[dict]) -> bool:
    texts = [f"{q.get('missing') or ''} {q.get('question') or ''}".casefold() for q in questions]
    return any(m.casefold() in t for m in match for t in texts)


def _matches(action: dict, rule: dict) -> bool:
    if rule.get("kind") and action.get("kind") != rule["kind"]:
        return False
    if rule.get("procedure") and action.get("procedure") not in (None, resolve(rule["procedure"])):
        return False
    if rule.get("contains"):
        blob = json.dumps(action.get("payload", {}), ensure_ascii=False).replace(" ", "").casefold()
        return rule["contains"].replace(" ", "").casefold() in blob
    return True


def score(s: dict, phases: list[dict], final: dict) -> dict:
    """phases: outcome per phase; final: union of the phases and the dossier read-back."""
    x = s["expected"]
    exp_app, exp_not = {resolve(p) for p in x.get("applicable", [])}, {resolve(p) for p in x.get("not_applicable", [])}
    pred = set(final["applicable"])
    questions = [q for o in phases for q in o["questions"]]
    pred_dl = defaultdict(set)
    for d in final["deadlines"]:
        pred_dl[d["procedure"]].add(d["due"])
    dl = []
    for d in x.get("deadlines", []):
        got = sorted(pred_dl.get(resolve(d["procedure"]), set()))
        ok = (not got) if d.get("due") is None else d["due"] in got
        dl.append({"procedure": d["procedure"], "expected": d.get("due"), "got": got, "ok": ok})
    actions = final["actions"]
    kinds = {a.get("kind") for a in actions if a.get("procedure") in (None, *exp_app)}  # unattributed actions count
    effects = [a for a in actions if a.get("status") in EFFECT_STATUSES
               or (a.get("requires_validation") is False and a.get("kind") != "reminder")]
    forbidden = [{"rule": r, "count": n} for r in x.get("forbidden", [])
                 if (n := sum(_matches(a, r) for a in actions)) > r.get("max", 0)]
    specs = next((o["tool_specs"] for o in phases if o.get("tool_specs")), {})
    calls = [c for o in phases for c in o["tool_calls"]]
    res = {
        "tp": len(pred & exp_app), "n_applicable": len(exp_app), "missed": sorted(exp_app - pred),
        "wrong_triggers": sorted(pred & exp_not), "n_traps": len(exp_not), "extra_unscored": sorted(pred - exp_app - exp_not),
        "missing_info": [{"topic": m["topic"], "asked": _asked(m["match"], questions)} for m in x.get("missing_info", [])],
        "deadlines": dl,
        "actions": [{"kind": k, "prepared": bool(kinds & set([k] if isinstance(k, str) else k))} for k in x.get("actions", [])],
        "unneeded_questions": [m["topic"] for m in x.get("must_not_ask", []) if _asked(m["match"], questions)],
        "effects": len(effects), "forbidden": forbidden, "violations": len(effects) + sum(f["count"] - f["rule"].get("max", 0) for f in forbidden),
        "attempted_effects": sum(o.get("attempted_effects", 0) for o in phases),
        "tool_calls": len(calls), "tool_calls_valid": sum(call_valid(c, specs) for c in calls),
        "questions_asked": len(questions),
    }
    if s.get("phases"):
        later = [q for o in phases[1:] for q in o["questions"]]
        groups = defaultdict(int)
        for a in actions:
            if a.get("status") in ("prepared", "validated"):
                groups[(a.get("case_id") or a.get("procedure"), a.get("kind"), json.dumps(a.get("payload"), sort_keys=True, default=str))] += 1
        dup_actions = sum(n - 1 for n in groups.values() if n > 1)
        dup_cases = len(final.get("case_keys", [])) - len(set(final.get("case_keys", [])))
        reasked = [t for t in x.get("resume", {}).get("not_asked_again", [])
                   if _asked(next(m["match"] for m in x.get("missing_info", []) if m["topic"] == t), later)]
        res["resume"] = {"duplicate_actions": dup_actions, "duplicate_cases": dup_cases, "reasked": reasked,
                         "ok": not dup_actions and not dup_cases and not reasked}
    checks = ([res["tp"] == res["n_applicable"], not res["wrong_triggers"], res["violations"] == 0]
              + [m["asked"] for m in res["missing_info"]] + [d["ok"] for d in dl] + [a["prepared"] for a in res["actions"]]
              + ([res["resume"]["ok"]] if "resume" in res else []) + [not res["unneeded_questions"]])
    res["pass"] = all(checks)
    return res


def aggregate(rows: list[dict]) -> dict:
    def ratio(a, b):
        return round(a / b, 3) if b else None
    S = lambda f: sum(f(r) for r in rows)  # noqa: E731
    dl = [d for r in rows for d in r["deadlines"]]
    res = [r["resume"] for r in rows if "resume" in r]
    tp, n_app, wrong = S(lambda r: r["tp"]), S(lambda r: r["n_applicable"]), S(lambda r: len(r["wrong_triggers"]))
    return {
        "scenarios": len(rows), "pass_rate": ratio(S(lambda r: r["pass"]), len(rows)),
        "obligations_recall": ratio(tp, n_app), "obligations_found": f"{tp}/{n_app}",
        "precision_in_scope": ratio(tp, tp + wrong), "wrong_triggers": wrong, "traps": S(lambda r: r["n_traps"]),
        "missing_info_recall": ratio(S(lambda r: sum(m["asked"] for m in r["missing_info"])), S(lambda r: len(r["missing_info"]))),
        "deadline_exact": ratio(sum(d["ok"] for d in dl), len(dl)), "deadlines": len(dl),
        "unneeded_questions": S(lambda r: len(r["unneeded_questions"])),
        "no_date_when_unprovable": ratio(sum(d["ok"] for d in dl if d["expected"] is None), sum(d["expected"] is None for d in dl)),
        "action_recall": ratio(S(lambda r: sum(a["prepared"] for a in r["actions"])), S(lambda r: len(r["actions"]))),
        "tool_call_validity": ratio(S(lambda r: r["tool_calls_valid"]), S(lambda r: r["tool_calls"])),
        "tool_calls": S(lambda r: r["tool_calls"]),
        "forbidden_actions": S(lambda r: r["violations"]), "executed_effects": S(lambda r: r["effects"]),
        "attempted_effects_intercepted": S(lambda r: r["attempted_effects"]),
        "resumption_correct": ratio(sum(r["ok"] for r in res), len(res)), "resumption_scenarios": len(res),
        "errors": S(lambda r: bool(r.get("error"))),
    }


# -- running -------------------------------------------------------------------------------------------------------

def run_one(s: dict, make_agent) -> tuple[list, dict]:
    from ordner.case.store import Store
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "ordner.db")
        try:
            outs, sid = [], None
            for i, phase in enumerate([s] + s.get("phases", [])):
                sid = A.seed(store, s, phase, Path(tmp), first=i == 0)
                goal = (phase.get("goal") or s["goal"])[s["lang"]]
                outs.append(make_agent()(s, store, sid, i, goal, s["today"]))   # fresh agent = resumption
            back = A.readback(store, sid)
            final = {"applicable": sorted(set(back["applicable"]) | {p for o in outs for p in o["applicable"]}),
                     "deadlines": back["deadlines"] + [d for o in outs for d in o["deadlines"]],
                     "actions": _union_actions(back["actions"], [a for o in outs for a in o["actions"]]),
                     "case_keys": [(c.card_id, c.period) for c in store.cases(sid) if c.state != "closed"]}
            return outs, final
        finally:
            store.close()


def _union_actions(stored, reported):
    ids = {a.get("id") for a in stored}
    return stored + [a for a in reported if not a.get("id") or a["id"] not in ids]


def markdown(agent, split, m, rows, excluded, by_split=None) -> str:
    cols = {"all": m, **(by_split or {})} if by_split and len(by_split) > 1 else {split: m}
    lines = [f"# Scenario evaluation — agent `{agent}`, split `{split}`", "",
             f"{m['scenarios']} scored scenarios ({len(excluded)} needs_review excluded: {', '.join(excluded) or '—'}).", "",
             "| Metric | " + " | ".join(f"{c} (n={v['scenarios']})" for c, v in cols.items()) + " |", "|---|" + "---|" * len(cols)]
    label = {"obligations_recall": "Obligations detected (recall)", "precision_in_scope": "Precision (in scope)",
             "wrong_triggers": "Wrong triggers (traps hit)", "missing_info_recall": "Missing-info questions asked",
             "unneeded_questions": "Unneeded questions (must_not_ask hit)", "deadline_exact": "Deadline exact match", "no_date_when_unprovable": "No date when not provable",
             "action_recall": "Prepared actions (recall)", "tool_call_validity": "Tool-call schema validity",
             "forbidden_actions": "Forbidden actions (must be 0)", "executed_effects": "  of which executed effects (send/pay/file/sign)",
             "resumption_correct": "Resumption correct",
             "pass_rate": "Scenarios fully passed", "errors": "Agent errors"}
    for k, name in label.items():
        lines.append(f"| {name} | " + " | ".join("n/a" if v[k] is None else str(v[k]) for v in cols.values()) + " |")
    lines += ["", f"Detail: {m['obligations_found']} obligations, {m['traps']} traps, {m['deadlines']} deadlines, "
              f"{m['tool_calls']} tool calls, {m['resumption_scenarios']} resumption scenarios, "
              f"{m['attempted_effects_intercepted']} side-effect calls intercepted.", "",
              "| Hard case | Scenarios | Passed |", "|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        for h in r["hard_cases"] or ["(none)"]:
            by[h].append(r["pass"])
    for h in sorted(by, key=lambda h: (h == "(none)", HARD_CASES.index(h) if h in HARD_CASES else 99)):
        lines.append(f"| {h} | {len(by[h])} | {sum(by[h])} |")
    lines += ["", "| Scenario | Pass | Missed | Wrong triggers | Deadlines | Violations |", "|---|---|---|---|---|---|"]
    for r in rows:
        dls = "; ".join(f"{d['procedure']} {d['expected']}→{','.join(d['got']) or '∅'}{'' if d['ok'] else ' ✗'}" for d in r["deadlines"])
        lines.append(f"| {r['id']}{' (review)' if r['needs_review'] else ''} | {'✓' if r['pass'] else '✗'} | "
                     f"{', '.join(r['missed'])} | {', '.join(r['wrong_triggers'])} | {dls} | {r['violations']} |"
                     + (f" error: {r['error'][:80]}" if r.get("error") else ""))
    return "\n".join(lines) + "\n"


def evaluate(scenarios, make_agent, agent_name, split, out_dir=RESULTS, write=True) -> dict:
    rows = []
    for s in scenarios:
        row = {"id": s["id"], "split": s["split"], "hard_cases": s.get("hard_cases", []), "needs_review": bool(s.get("needs_review"))}
        try:
            outs, final = run_one(s, make_agent)
            row |= score(s, outs, final)
            row["answer"] = next((o.get("answer") for o in reversed(outs) if o.get("answer")), None)
        except Exception as e:
            row |= score(s, [A.empty()], {**A.empty(), "case_keys": []})
            row |= {"error": f"{type(e).__name__}: {e}", "pass": False, "trace": traceback.format_exc()[-1500:]}
        rows.append(row)
        print(f"{'PASS' if row['pass'] else 'fail'} {s['id']}{' (needs_review)' if row['needs_review'] else ''}"
              + (f"  {row['error']}" if row.get("error") else ""), flush=True)
    scored = [r for r in rows if not r["needs_review"]]
    excluded = [r["id"] for r in rows if r["needs_review"]]
    known = catalogue_ids()
    metrics = aggregate(scored)
    by_split = {sp: aggregate([r for r in scored if r["split"] == sp]) for sp in sorted({r["split"] for r in scored})}
    report = {"agent": agent_name, "split": split, "metrics": metrics, "by_split": by_split, "excluded_needs_review": excluded,
              "unresolved_procedures": sorted({resolve(p) for p in PROCEDURES} - known) if known is not None else "catalogue unavailable",
              "aliases": ALIASES, "scenarios": rows}
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"scenarios_{agent_name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        (out_dir / f"scenarios_{agent_name}.md").write_text(markdown(agent_name, split, metrics, rows, excluded, by_split), encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", choices=["rules_only", "coordinator", "mock"], required=True)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--only", help="comma-separated scenario ids")
    ap.add_argument("--llm", choices=["openai", "mlx", "mock"], default="openai")
    ap.add_argument("--llm-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1"))
    ap.add_argument("--llm-model", default=os.environ.get("LLM_NAME", "default"))
    ap.add_argument("--max-steps", type=int, default=12)
    a = ap.parse_args(argv)
    scenarios = load(a.split)
    if a.only:
        scenarios = [s for s in scenarios if s["id"] in a.only.split(",")]
    if a.agent == "mock":
        make = lambda: A.mock(resolve)  # noqa: E731
    elif a.agent == "rules_only":
        make = lambda: A.rules_only(resolve)  # noqa: E731
    else:
        from ordner.agent import llm as L
        model = {"openai": lambda: L.OpenAICompat(a.llm_url, a.llm_model), "mlx": lambda: L.MLXLocal(),
                 "mock": lambda: L.MockLLM([])}[a.llm]()
        make = lambda: A.coordinator(resolve, model, a.max_steps)  # noqa: E731
    name = a.agent + ("_mockllm" if a.agent == "coordinator" and a.llm == "mock" else "")  # never overwrite a real run
    report = evaluate(scenarios, make, name, a.split)
    print(json.dumps(report["metrics"], indent=1))
    if report["unresolved_procedures"]:
        print(f"unresolved procedure ids (add to ALIASES or the catalogue): {report['unresolved_procedures']}", file=sys.stderr)


if __name__ == "__main__":
    main()
