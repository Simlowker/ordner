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


def main(argv=None):
    from ordner.eval.scenarios.run import resolve
    from ordner.harness.experts import EXPERTS

    ap = argparse.ArgumentParser()
    ap.add_argument("--kept", default=str(OUT / "kept.jsonl"))
    ap.add_argument("--variants", nargs="+", default=[str(OUT / "variants.jsonl"), str(OUT / "variants2.jsonl")])
    a = ap.parse_args(argv)
    variants = {v["id"]: v for path in a.variants for v in read_jsonl(path)}
    groups = {}
    for t in read_jsonl(a.kept):
        eid = expert_of(procedures(variants[t["variant_id"]], resolve), EXPERTS)
        groups.setdefault(eid, []).append(t)
    for eid, rows in groups.items():
        if eid:
            write_jsonl(OUT / "experts" / eid / "kept.jsonl", rows)
    print({eid or "coordinator only": len(rows) for eid, rows in groups.items()})
    print("by source:", Counter((eid or "-", t["source_id"]) for eid, rows in groups.items() for t in rows).most_common(40))


if __name__ == "__main__":
    main()
