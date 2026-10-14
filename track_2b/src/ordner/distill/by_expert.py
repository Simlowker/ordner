"""Split kept teacher trajectories by expert (ordner.harness.experts): a trajectory goes to an expert when every
procedure its variant expects starts with one of that expert's card prefixes; cross-domain ones stay with the coordinator.

    PYTHONPATH=src .venv/bin/python -m ordner.distill.by_expert [--kept work/distill/kept.jsonl] [--variants a.jsonl ...]

Writes work/distill/experts/<id>/kept.jsonl and prints the counts."""
import argparse
from collections import Counter

from . import OUT, read_jsonl, write_jsonl


def procedures(variant, resolve=lambda c: c):
    x = variant.get("expected") or {}
    cards = (set(x.get("applicable", [])) | {d["procedure"] for d in x.get("deadlines", []) if isinstance(d, dict)}
             | {a["procedure"] for a in x.get("actions", []) if isinstance(a, dict) and a.get("procedure")})
    return {resolve(c) for c in (cards or set(x.get("not_applicable", [])))}


def expert_of(cards, experts):
    if not cards:
        return None
    for e in experts.values():
        if "*" not in e.cards and all(any(c.startswith(p) for p in e.cards) for c in cards):
            return e.id
    return None


def for_expert(traj, expert, system_prompt):
    """The trajectory as the expert sees it at inference: its system prompt and only its tools (model-side names).
    None when the teacher called a tool outside the expert's set (the student would learn a call it cannot make)."""
    keep = {t.replace(".", "_") for t in expert.tools} | {"ask_user", "prepare_action"}
    phases = []
    for ph in traj["phases"]:
        calls = {c["name"] for t in ph["turns"] for c in t["reply"].get("tool_calls") or []}
        if calls - keep:
            return None
        msgs = [{**ph["messages"][0], "content": system_prompt}] + ph["messages"][1:]
        phases.append({**ph, "messages": msgs, "tools": [t for t in ph["tools"] if t["function"]["name"] in keep]})
    return {**traj, "phases": phases, "expert": expert.id}


def main(argv=None):
    from ordner.eval.scenarios.run import resolve
    from ordner.harness.experts import EXPERTS, system_prompt

    ap = argparse.ArgumentParser()
    ap.add_argument("--kept", default=str(OUT / "kept.jsonl"))
    ap.add_argument("--variants", nargs="+", default=[str(OUT / "variants.jsonl"), str(OUT / "variants2.jsonl")])
    a = ap.parse_args(argv)
    variants = {v["id"]: v for path in a.variants for v in read_jsonl(path)}
    groups = {}
    for t in read_jsonl(a.kept):
        eid = expert_of(procedures(variants[t["variant_id"]], resolve), EXPERTS)
        groups.setdefault(eid, []).append(t)
    dropped = {}
    for eid, rows in groups.items():
        if eid:
            seen = [x for x in (for_expert(t, EXPERTS[eid], system_prompt(eid)) for t in rows) if x]
            dropped[eid] = len(rows) - len(seen)
            write_jsonl(OUT / "experts" / eid / "kept.jsonl", seen)
    print("dropped (tool outside the expert's set):", dropped)
    print({eid or "coordinator only": len(rows) for eid, rows in groups.items()})
    print("by source:", Counter((eid or "-", t["source_id"]) for eid, rows in groups.items() for t in rows).most_common(40))


if __name__ == "__main__":
    main()
