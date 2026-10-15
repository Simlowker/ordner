"""Keep only verified teacher trajectories: the variant's scenario metrics must all pass, the loop must end cleanly,
and the model must have made no tool-use mistake (otherwise the student learns the mistake).

    PYTHONPATH=src .venv/bin/python -m ordner.distill.filter work/distill/traj.apertus70b.jsonl [more.jsonl ...]

Writes work/distill/kept.jsonl (kept trajectories, every input file merged) and work/distill/filter_report.json
(rejection reasons, counts per teacher and per source scenario).
"""
import argparse
import json
from collections import Counter, defaultdict

from . import OUT, read_jsonl, write_jsonl

# coordinator / registry answers that mean the model itself erred (bad JSON, unknown tool, invalid arguments,
# duplicate call, unknown card); a document that cannot be decoded is the environment, not a model error
MODEL_ERRORS = ("valid JSON", "unknown tool", "missing required argument", "must be of type", "must be one of",
                "this exact call was already made", "invalid arguments", "unknown procedure card", "unknown case_id",
                "several cases are open")
NEVER_TRAIN = {"claude", "claude-code"}   # closed model, ceiling check only: never training data (AGENTS.md rule 6)
BAD_NOTES = {"date(s) in the answer found in no tool result": "ungrounded_date", "max_steps=": "max_steps",
             "kept repeating": "repeating"}


def _error(content):
    try:
        res = json.loads(content).get("result")
    except (json.JSONDecodeError, AttributeError):   # clipped long result: not an error message
        return None
    return str(res.get("error") or "") if isinstance(res, dict) else None


def reasons(r) -> list[str]:
    """Why a trajectory is rejected; empty list = keep."""
    if r.get("error"):
        return [f"error: {r['error'][:80]}"]
    s, out = r["score"], []
    out += [f"missed: {p}" for p in s["missed"]]
    out += [f"wrong_trigger: {p}" for p in s["wrong_triggers"]]
    out += [f"deadline: {d['procedure']} expected {d['expected']} got {d['got']}" for d in s["deadlines"] if not d["ok"]]
    out += [f"question_not_asked: {m['topic']}" for m in s["missing_info"] if not m["asked"]]
    out += [f"action_missing: {a['kind']}" for a in s["actions"] if not a["prepared"]]
    out += [f"unneeded_question: {t}" for t in s["unneeded_questions"]]
    if s["violations"]:
        out.append(f"forbidden_action: {s['violations']}")
    if s.get("attempted_effects"):
        out.append("attempted_effect")
    if s["tool_calls_valid"] < s["tool_calls"]:
        out.append(f"invalid_tool_call: {s['tool_calls'] - s['tool_calls_valid']}")
    if "resume" in s and not s["resume"]["ok"]:
        out.append("resume")
    for o in r["outs"]:
        for note in o.get("notes") or []:
            out += [tag for pat, tag in BAD_NOTES.items() if pat in note]
    for ph in r["phases"]:
        for m in ph["messages"]:
            err = _error(m["content"]) if m["role"] == "tool" else None
            out += [f"tool_error: {pat}" for pat in MODEL_ERRORS if err and pat in err]
    last = r["outs"][-1] if r["outs"] else {}
    if not last.get("answer") and not last.get("questions"):
        out.append("no_answer")
    if not out and not s["pass"]:
        out.append("score_fail")   # safety net: a check the runner adds later
    return list(dict.fromkeys(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("traj", nargs="+")
    ap.add_argument("--out", default=str(OUT / "kept.jsonl"))
    ap.add_argument("--report", default=str(OUT / "filter_report.json"))
    a = ap.parse_args(argv)
    rows = [r for p in a.traj for r in read_jsonl(p) if r["teacher"] not in NEVER_TRAIN]
    kept, why, by_teacher, by_source = [], Counter(), defaultdict(Counter), defaultdict(Counter)
    for r in rows:
        rs = reasons(r)
        by_teacher[r["teacher"]]["kept" if not rs else "rejected"] += 1
        by_source[r["source_id"]]["kept" if not rs else "rejected"] += 1
        for x in rs:
            why[x.split(":")[0]] += 1
        r["rejected"] = rs
        if not rs:
            kept.append(r)
    write_jsonl(a.out, kept)
    report = {"inputs": a.traj, "trajectories": len(rows), "kept": len(kept), "reasons": dict(why.most_common()),
              "by_teacher": {k: dict(v) for k, v in by_teacher.items()},
              "by_source": {k: dict(v) for k, v in sorted(by_source.items())},
              "rejected": [{"variant_id": r["variant_id"], "teacher": r["teacher"], "reasons": r["rejected"]}
                           for r in rows if r["rejected"]]}
    with open(a.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"kept {len(kept)}/{len(rows)} -> {a.out}; reasons {dict(why.most_common())}; report {a.report}")


if __name__ == "__main__":
    main()
